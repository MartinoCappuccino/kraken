import krakenex
import pandas as pd
import os
import sqlalchemy
import json
from time import sleep
from datetime import datetime, timezone
from dotenv import load_dotenv
from threading import Thread
from queue import Queue
from pykrakenapi import KrakenAPI
import os
import platform

from sqlalchemy.sql.sqltypes import Float, String
os.environ['MPLCONFIGDIR'] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import logging
import logging.config

def load_data(Symbols, event_queue_data, event_queue_strat):
    logging.info("Tracking assets: {}".format(Symbols))
    if os.path.exists("Data.db"):
        os.remove("Data.db")
    sql_engine = sqlalchemy.create_engine("sqlite:///Data.db")
    Frame = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice', 'TrackPrice', 'SellPriceHigh', 'SellPriceLow', 'Open_position', 'Profit'])
    Frame.Symbol = Frame.Symbol.astype(str)
    Frame.Price = Frame.Price.astype(float)
    Frame.Time = pd.to_datetime(Frame.Time)
    Frame.TrackPrice = Frame.TrackPrice.astype(float)
    Frame.BuyPrice = Frame.BuyPrice.astype(float)
    Frame.SellPriceHigh = Frame.SellPriceHigh.astype(float)
    Frame.SellPriceLow = Frame.SellPriceLow.astype(float)
    Frame.Open_position = Frame.Open_position.astype(bool)
    Frame.Profit = Frame.Profit.astype(float)
    Frame.to_sql("Strategy", sql_engine, if_exists="append", index=False)
    while True:
        try:
            if event_queue_data.get() == 1:
                print("data")
                for Symbol in Symbols:
                    Symbol_time_start = round(datetime.now(timezone.utc).astimezone().timestamp() * 1000)
                    
                    Data = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice'])
                    
                    Symboldata = kraken.get_ticker_information(Symbol)
                    Data = Data.append({"Symbol" : Symbol, "Price" : Symboldata['a'][0][0], "Time" : pd.to_datetime(Symbol_time_start, unit = 'ms'), "BuyPrice": 0}, ignore_index = True)
                    Data.Price = Data.Price.astype(float)
                    Data.BuyPrice = Data.BuyPrice.astype(float)
                    Data.to_sql(Symbol, sql_engine, if_exists="append", index=False)

                    Symbol_time_end = round(datetime.now(timezone.utc).astimezone().timestamp() * 1000)
                    Symbol_time_diff = Symbol_time_end - Symbol_time_start
                    if Symbol_time_diff < 1000:
                        wait_time = (1000 - Symbol_time_diff)/1000 + 0.01
                        sleep(wait_time)
                        
                event_queue_strat.put(1)
        except Exception as e:
            logging.error(e)
            break
        except KeyboardInterrupt:
            break

def strategyChange(Symbols, entry, capital, profit_margin, lookback, event_queue_strat, event_queue_plot):
    logging.info("Time frame is set at {} seconds.".format(lookback))
    logging.info("Buying for {} euros.".format(capital))
    logging.info("Buying when change is greater than {}%.".format(entry*100))
    logging.info("Selling when change is greater than {}%.".format(profit_margin*100))
    sql_engine = sqlalchemy.create_engine("sqlite:///Data.db")
    while True:
        try:
            if event_queue_strat.get() == 1:
                print("strat")
                for Symbol in Symbols:
                    StrategyData = pd.read_sql_table("Strategy", sql_engine)
                    Data = pd.read_sql_table(Symbol, sql_engine)
                    if Data.Price.last_valid_index() >= lookback:
                        if len(StrategyData) == 0:
                            open_position = False
                        else:
                            open_position = StrategyData.Open_position.iloc[-1]

                        if not open_position:
                            StartPrice = Data.Price.iloc[-lookback]
                            LastPrice = Data.Price.iloc[-1]

                            BuyChange = LastPrice / StartPrice - 1
                            Data.at[Data.index[-1],'BuyPrice'] = (entry+1) * LastPrice
                            if BuyChange > entry:
                                #order = kraken.add_standard_order(pair=Symbol, type='buy', ordertype='limit', volume='0.007', price=qty, validate=False)
                                #print(order)
                                quantity = capital/LastPrice
                                BuyPrice = LastPrice

                                logging.info("{} {} bought at {} euros.".format(quantity, Symbol, LastPrice))

                                Frame = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice', 'TrackPrice', 'SellPriceHigh', 'SellPriceLow', 'Open_position', 'Profit'])
                                Frame = Frame.append({"Symbol" : Symbol, "Price" : LastPrice, "Time" : pd.to_datetime(round(datetime.now(timezone.utc).astimezone().timestamp() * 1000), unit = 'ms'), "BuyPrice": BuyPrice, "TrackPrice": 0, "SellPriceHigh": 0, "SellPriceLow": 0, "Open_position": True, "Profit": 0}, ignore_index = True)
                                Frame.Price = Frame.Price.astype(float)
                                Frame.TrackPrice = Frame.TrackPrice.astype(float)
                                Frame.BuyPrice = Frame.BuyPrice.astype(float)
                                Frame.SellPriceHigh = Frame.SellPriceHigh.astype(float)
                                Frame.SellPriceLow = Frame.SellPriceLow.astype(float)
                                Frame.Profit = Frame.Profit.astype(float)
                                Frame.to_sql("Strategy", sql_engine, if_exists="append", index=False)

                            else:
                                logging.info("Not buying {} yet.".format(Symbol))

                        elif open_position:
                            if Symbol == StrategyData.Symbol.iloc[-1]:
                                LastPrice = StrategyData.Price.iloc[-1]
                                BuyPrice = StrategyData.BuyPrice.iloc[-1]
                                TrackPrice = StrategyData.TrackPrice.iloc[-1]
                                if TrackPrice >= BuyPrice:
                                    TrackPrice = TrackPrice
                                elif LastPrice >= StrategyData.SellPriceHigh.iloc[-1]:
                                    TrackPrice = LastPrice
                                else:
                                    TrackPrice = BuyPrice
                                SellChange = LastPrice / TrackPrice - 1
                                SellPriceHigh = (1+profit_margin) * TrackPrice
                                SellPriceLow = (1-profit_margin) * TrackPrice
                                if SellChange >= profit_margin:
                                    #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                                    #print(order)
                                    Profit = LastPrice - BuyPrice
                                    logging.info("{} {} sold with profit of {} euros.".format(quantity, Symbol, Profit))
                                    Profit = StrategyData["Profit"].iloc[-1] + Profit
                                    open_position = False
                                    logging.info("Total profit is {} euros".format(Profit))
                                elif SellChange <= -profit_margin:
                                    Loss = LastPrice - BuyPrice
                                    logging.info("{} sold with loss of {} euros.".format(Symbol, Loss))
                                    Profit = StrategyData["Profit"].iloc[-1] + Loss
                                    open_position = False
                                    logging.info("Total profit is {} euros".format(Profit))
                                else:
                                    open_position = True
                                    Profit = StrategyData["Profit"].iloc[-1]
                                
                                Frame = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice', 'TrackPrice', 'SellPriceHigh', 'SellPriceLow', 'Open_position', 'Profit'])
                                Frame = Frame.append({"Symbol" : Symbol, "Price" : LastPrice, "Time" : pd.to_datetime(round(datetime.now(timezone.utc).astimezone().timestamp() * 1000), unit = 'ms'), "BuyPrice": BuyPrice, "TrackPrice": TrackPrice, "SellPriceHigh": SellPriceHigh, "SellPriceLow": SellPriceLow, "Open_position": open_position, "Profit": Profit}, ignore_index = True)
                                Frame.Price = Frame.Price.astype(float)
                                Frame.TrackPrice = Frame.TrackPrice.astype(float)
                                Frame.BuyPrice = Frame.BuyPrice.astype(float)
                                Frame.SellPriceHigh = Frame.SellPriceHigh.astype(float)
                                Frame.SellPriceLow = Frame.SellPriceLow.astype(float)
                                Frame.Profit = Frame.Profit.astype(float)
                                Frame.to_sql("Strategy", sql_engine, if_exists="append", index=False)   

                    Data.to_sql(Symbol, sql_engine, if_exists="replace", index=False)   
                event_queue_plot.put(1)
        except Exception as e:
            logging.error(e)
            break
        except KeyboardInterrupt:
            break    

def Plot(Symbols, lookback, event_queue_plot, event_queue_data):
    sql_engine = sqlalchemy.create_engine("sqlite:///Data.db")
    fig, ax = plt.subplots(2, len(Symbols), num="Kraken")
    plt.ion()
    plt.show(block=False)
    while True:
        try:
            if event_queue_plot.get() == 1:
                StrategyData = pd.read_sql_table("Strategy", sql_engine)
                if len(StrategyData) == 0:
                    open_position = False
                else:
                    open_position = StrategyData.Open_position.iloc[-1]

                if open_position == True:
                    i=0
                    Symbol = StrategyData.Symbol.iloc[-1]
                    Data = pd.read_sql_table(Symbol, sql_engine)
                    ax[0, i].cla()
                    ax[1, i].cla()
                    x = Data["Time"]
                    y = Data["Price"]
                    ax[0, i].plot(x, y, color='blue', label="Price")
                    ax[0, i].axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                    ax[0, i].legend()
                    ax[0, i].set_title(Symbol+" price.")
                    ax[0, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                    ax[0, i].tick_params('x', labelrotation = 45)
                    x = StrategyData["Time"]
                    y = StrategyData["Price"]
                    ax[1, i].plot(x, y, color='blue', label="Price")
                    ax[1, i].plot(x, StrategyData["SellPriceHigh"].iloc[-lookback:], color = 'green', linestyle = '--', label = "SellPriceHigh")
                    ax[1, i].plot(x, StrategyData["SellPriceLow"].iloc[-lookback:], color = 'red', linestyle = '--', label = "SellPriceLow")
                    ax[1, i].plot(x, StrategyData["TrackPrice"].iloc[-lookback:], color = "orange", linestyle = '--', label = "TrackPrice")
                    ax[1, i].axhline(y=StrategyData["BuyPrice"].iloc[-1], color = 'black', linestyle = '--', label = "BuyPrice")
                    ax[1, i].axis([min(x), max(x), StrategyData["SellPriceLow"].iloc[-1]-StrategyData["Price"].mean()/2000, StrategyData["SellPriceHigh"].iloc[-1]+StrategyData["Price"].mean()/2000])
                    ax[1, i].legend()
                elif open_position == False:
                    i=0
                    for Symbol in Symbols:
                        Data = pd.read_sql_table(Symbol, sql_engine)
                        ax[0, i].cla()
                        ax[1, i].cla()
                        if Data.Price.last_valid_index() >= lookback and Data.Price.last_valid_index() >= 2:
                            NewData = Data.iloc[-lookback:]
                            x = NewData["Time"]
                            y = NewData["Price"]
                            ax[1, i].plot(x, y, color='blue', label="Price")
                            ax[1, i].axhline(y=NewData["BuyPrice"].iloc[-1], color = 'black', linestyle = '--', label = "BuyPrice")
                            ax[1, i].axis([min(x), max(x), NewData["Price"].min()-NewData["Price"].mean()/2000, NewData["BuyPrice"].iloc[-1]+NewData["Price"].mean()/2000])
                            ax[1, i].legend()
                            ax[1, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                            ax[1, i].tick_params('x', labelrotation = 45)
                            ax[1, i].set_title(Symbol+" price.")
                            plt.draw()
                            plt.pause(0.001)

                        if Data.Price.last_valid_index() >= 2:
                            x = Data["Time"]
                            y = Data["Price"]
                            ax[0, i].plot(x, y, color='blue', label="Price")
                            ax[0, i].axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                            ax[0, i].legend()
                            ax[0, i].set_title(Symbol+" price.")
                            ax[0, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                            ax[0, i].tick_params('x', labelrotation = 45)
                            plt.draw()
                            plt.pause(0.001)

                        i=i+1 
                event_queue_data.put(1)
        except Exception as e:
            logging.error(e)
            break
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    api = krakenex.API()
    api.load_key('kraken_api_key.txt')
    kraken = KrakenAPI(api)

    logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
    })
    logging.basicConfig(format='%(asctime)s - {} - [Kraken] - [%(levelname)s] - %(message)s'.format(platform.uname()[1]), datefmt='%m/%d/%Y %I:%M:%S', level=logging.DEBUG)

    load_dotenv(dotenv_path="kraken.env")
    SYMBOLS = json.loads(os.getenv("SYMBOLS"))
    LOOKBACK = int(os.getenv("LOOKBACK"))
    ENTRY = float(os.getenv("ENTRY"))
    CAPITAL = float(os.getenv("CAPITAL"))
    PROFIT_MARGIN = float(os.getenv("PROFIT_MARGIN"))

    event_queue_data = Queue()
    event_queue_strat = Queue()
    event_queue_plot = Queue()
    
    event_queue_data.put(1)
    Thread(target=load_data, args=(SYMBOLS, event_queue_data, event_queue_strat)).start()
    Thread(target=strategyChange, args=(SYMBOLS, ENTRY, CAPITAL, PROFIT_MARGIN, LOOKBACK, event_queue_strat, event_queue_plot)).start()
    Plot(SYMBOLS, LOOKBACK, event_queue_plot, event_queue_data)
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
os.environ['MPLCONFIGDIR'] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt
import logging
import logging.config

def load_data(Symbols, event_queue_data, event_queue_strat):
    logging.info("Tracking assets: {}".format(Symbols))
    for Symbol in Symbols:
        if os.path.exists(Symbol+"stream.db"):
            os.remove(Symbol+"stream.db")
    while True:
        try:
            if event_queue_data.get() == 1:
                for Symbol in Symbols:
                    Symbol_time_start = round(datetime.now(timezone.utc).astimezone().timestamp() * 1000)

                    sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")
                    
                    Data = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice', 'TrackPrice', 'SellPriceHigh', 'SellPriceLow', 'Open_position', 'Profit'])
                    
                    Symboldata = kraken.get_ticker_information(Symbol)
                    Data = Data.append({"Symbol" : Symbol, "Price" : Symboldata['a'][0][0], "Time" : pd.to_datetime(Symbol_time_start, unit = 'ms'), "BuyPrice": 0, "TrackPrice": 0, "SellPriceHigh": 0, "SellPriceLow": 0, "Open_position": False, "Profit": 0}, ignore_index = True)
                    Data.Price = Data.Price.astype(float)
                    Data.TrackPrice = Data.TrackPrice.astype(float)
                    Data.BuyPrice = Data.BuyPrice.astype(float)
                    Data.SellPriceHigh = Data.SellPriceHigh.astype(float)
                    Data.SellPriceLow = Data.SellPriceLow.astype(float)
                    Data.Profit = Data.Profit.astype(float)
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
    while True:
        try:
            if event_queue_strat.get() == 1:
                for Symbol in Symbols:
                    sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

                    Data = pd.read_sql(Symbol, sql_engine)

                    if Data.Price.last_valid_index() >= lookback:
                        open_position = Data.Open_position.iloc[-2]
                        if not open_position:
                            StartPrice = Data.Price.iloc[-lookback]
                            LastPrice = Data.Price.iloc[-2]

                            BuyChange = LastPrice / StartPrice - 1
                            Data.at[Data.index[-1],'BuyPrice'] = (entry+1) * LastPrice
                            if BuyChange > entry:
                                #order = kraken.add_standard_order(pair=Symbol, type='buy', ordertype='limit', volume='0.007', price=qty, validate=False)
                                #print(order)
                                quantity = capital/LastPrice
                                BuyPrice = LastPrice

                                logging.info("{} {} bought at {} euros.".format(quantity, Symbol, LastPrice))
                                
                                Data.at[Data.index[-1],'BuyPrice'] = BuyPrice
                                Data.at[Data.index[-1],'Open_position'] = True
                            else:
                                logging.info("Not buying {} yet.".format(Symbol))

                        if open_position:
                            LastPrice = Data.Price.iloc[-2]
                            if LastPrice >= Data.at[Data.index[-2], 'SellPriceHigh']:
                                TrackPrice = LastPrice
                                Data.at[Data.index[-1], "TrackPrice"] = TrackPrice
                            else:
                                TrackPrice = BuyPrice
                                Data.at[Data.index[-1], "TrackPrice"] = TrackPrice
                            SellChange = LastPrice / TrackPrice - 1
                            Data.at[Data.index[-1],'SellPriceHigh'] = (1+profit_margin) * TrackPrice
                            Data.at[Data.index[-1],'SellPriceLow'] = (1-profit_margin) * TrackPrice
                            if SellChange >= profit_margin:
                                #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                                #print(order)
                                Profit = LastPrice - BuyPrice
                                logging.info("{} sold with profit of {} euros.".format(Symbol, Profit))
                                Data.at[Data.index[-1],'Open_position'] = False
                                print(Data)
                                Data.at[Data.index[-1],'Profit'] = Data["Profit"].iloc[-2] + Profit
                                logging.info("Total profit is {} euros".format(Data.Profit.iloc[-1]))
                            if SellChange <= -profit_margin:
                                Loss = LastPrice - BuyPrice
                                logging.info("{} sold with loss of {} euros.".format(Symbol, Loss))
                                Data.at[Data.index[-1],'Profit'] = Data["Profit"].iloc[-2] + Loss
                                Data.at[Data.index[-1],'Open_position'] = False
                                print(Data)
                                logging.info("Total profit is {} euros".format(Data.Profit.iloc[-1]))
                            else:
                                Data.at[Data.index[-1],'Open_position'] = True
                            Data.at[Data.index[-1],'BuyPrice'] = BuyPrice
                    Data.to_sql(Symbol, sql_engine, if_exists="replace", index=False)
                event_queue_plot.put(1)
        except Exception as e:
            logging.error(e)
            break
        except KeyboardInterrupt:
            break    

def plot(Symbols, lookback, event_queue_plot, event_queue_data):
    while True:
        try:
            if event_queue_plot.get() == 1:
                for Symbol in Symbols:
                    sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

                    plt.ion()
                    plt.show(block=False)
                    plt.figure("Kraken")
                    Data = pd.read_sql(Symbol, sql_engine)
                    if Data.Price.last_valid_index() >= lookback and Data.Price.last_valid_index() >= 2:
                        NewData = Data.iloc[-lookback:]
                        x = NewData["Time"]
                        y = NewData["Price"]
                        plt.plot(x,y, color='blue')
                        if NewData["Open_position"].iloc[-1] == True:
                            plt.plot(x, NewData["SellPriceHigh"].iloc[-lookback:], color = 'green', linestyle = '--')
                            plt.plot(x, NewData["SellPriceLow"].iloc[-lookback:], color = 'red', linestyle = '--')
                            plt.plot(x, NewData["TrackPrice"].iloc[-lookback:], color = "orange", linestyle = '--')
                            plt.axhline(y=NewData["BuyPrice"].iloc[-1], color = 'black', linestyle = '--')
                            plt.axis([min(x), max(x), NewData["SellPriceLow"].iloc[-1]-NewData["Price"].mean()/2000, NewData["SellPriceHigh"].iloc[-1]+NewData["Price"].mean()/2000])
                        else:
                            plt.axhline(y=NewData["BuyPrice"].iloc[-1], color = 'black', linestyle = '--')
                            plt.axis([min(x), max(x), NewData["Price"].min()-NewData["Price"].mean()/2000, NewData["BuyPrice"].iloc[-1]+NewData["Price"].mean()/2000])
                        plt.gcf().autofmt_xdate()
                        plt.title(Symbol+" price.")
                        plt.draw()
                        plt.pause(0.001)

                    elif Data.Price.last_valid_index() >= 2:
                        x = Data["Time"]
                        y = Data["Price"]
                        plt.axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                        plt.plot(x,y, color='blue')
                        plt.gcf().autofmt_xdate()
                        plt.title(Symbol+" price.")
                        plt.draw()
                        plt.pause(0.001)
                    plt.cla()
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
    logging.basicConfig(format='%(asctime)s - {} - [Kraken] - [%(levelname)s] - %(message)s'.format(os.uname()[1]), datefmt='%m/%d/%Y %I:%M:%S', level=logging.DEBUG)

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
    plot(SYMBOLS, LOOKBACK, event_queue_plot, event_queue_data)
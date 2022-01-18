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
os.environ['MPLCONFIGDIR'] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import logging
import logging.config



def Symbolstostring(Symbols):
    Symbolstring = ""
    for i in range(len(Symbols)):
        if i == len(Symbols)-1:
            Symbolstring = Symbolstring + Symbols[i]
        else:
            Symbolstring = Symbolstring + Symbols[i] + ","
    return Symbolstring


def load_data(Symbols, event_queue_data, event_queue_strat, time_end):
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
    Symbolstring = Symbolstostring(Symbols)
    while True:
        try:
            if event_queue_data.get() == 1:
                Symbol_time_start = round(datetime.now(timezone.utc).astimezone().timestamp() * 1000)                  
                Symbol_time_end = time_end.get()
                Symbol_time_diff = Symbol_time_end - Symbol_time_start
                if Symbol_time_diff < 0:
                    None
                elif Symbol_time_diff < 1000:
                    wait_time = (1000 - Symbol_time_diff)/1000 + 0.01
                    sleep(wait_time)
                
                Data = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice'])
                
                Symboldata = kraken.get_ticker_information(Symbolstring)
                for i in range(len(Symbols)):
                    Data = Data.append({"Symbol" : Symbols[i], "Price" : Symboldata.loc[Symbols[i], 'a'][0], "Time" : pd.to_datetime(Symbol_time_start, unit = 'ms'), "BuyPrice": 0}, ignore_index = True)
                    Data.Price = Data.Price.astype(float)
                    Data.BuyPrice = Data.BuyPrice.astype(float)
                    Data.to_sql(Symbols[i], sql_engine, if_exists="append", index=False)
                    Data = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice'])
            
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
    logging.info("Selling when change is greater than {}%.\n".format(profit_margin*100))
    sql_engine = sqlalchemy.create_engine("sqlite:///Data.db")
    while True:
        try:
            if event_queue_strat.get() == 1:
                for Symbol in Symbols:
                    StrategyData = pd.read_sql_table("Strategy", sql_engine)
                    Data = pd.read_sql_table(Symbol, sql_engine)
                    if Data.Price.last_valid_index() >= lookback:
                        if len(StrategyData) == 0:
                            open_position = False
                            Profit = 0
                        else:
                            open_position = StrategyData.Open_position.iloc[-1]
                            Profit = StrategyData.Profit.iloc[-1]

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
                                
                                FrameAppend = Data.iloc[-lookback:-1]
                                Frame = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice', 'TrackPrice', 'SellPriceHigh', 'SellPriceLow', 'Open_position', 'Profit'])
                                k = len(FrameAppend)
                                for i in range(len(FrameAppend)):
                                    Frame = Frame.append({"Symbol" : FrameAppend.Symbol.iloc[-k], "Price" : FrameAppend.Price.iloc[-k], "Time" : FrameAppend.Time.iloc[-k], "BuyPrice": FrameAppend.BuyPrice.iloc[-k], "TrackPrice": 0, "SellPriceHigh": 0, "SellPriceLow": 0, "Open_position": False, "Profit": Profit}, ignore_index = True)
                                    k=k-1
                                Frame = Frame.append({"Symbol" : Symbol, "Price" : LastPrice, "Time" : pd.to_datetime(round(datetime.now(timezone.utc).astimezone().timestamp() * 1000), unit = 'ms'), "BuyPrice": BuyPrice, "TrackPrice": 0, "SellPriceHigh": 0, "SellPriceLow": 0, "Open_position": True, "Profit": Profit}, ignore_index = True)
                                Frame.Price = Frame.Price.astype(float)
                                Frame.TrackPrice = Frame.TrackPrice.astype(float)
                                Frame.BuyPrice = Frame.BuyPrice.astype(float)
                                Frame.SellPriceHigh = Frame.SellPriceHigh.astype(float)
                                Frame.SellPriceLow = Frame.SellPriceLow.astype(float)
                                Frame.Profit = Frame.Profit.astype(float)
                                Frame.to_sql("Strategy", sql_engine, if_exists="append", index=False)

                        elif open_position:
                            if Symbol == StrategyData.Symbol.iloc[-1]:
                                LastPrice = Data.Price.iloc[-1]
                                BuyPrice = StrategyData.BuyPrice.iloc[-1]
                                TrackPrice = StrategyData.TrackPrice.iloc[-1]
                                if TrackPrice >= BuyPrice and LastPrice >= StrategyData.SellPriceHigh.iloc[-1] and TRAILING == True:
                                    TrackPrice = LastPrice
                                elif TrackPrice >= BuyPrice and TRAILING == True:
                                    TrackPrice = TrackPrice
                                else:
                                    TrackPrice = BuyPrice
                                SellChange = LastPrice / TrackPrice - 1
                                SellPriceHigh = (1+profit_margin) * TrackPrice
                                SellPriceLow = (1-profit_margin) * TrackPrice
                                if SellChange >= profit_margin:
                                    #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                                    #print(order)
                                    Profit = capital * SellChange
                                    logging.info("{} {} sold with profit of {} euros.".format(quantity, Symbol, Profit))
                                    Profit = StrategyData["Profit"].iloc[-1] + Profit
                                    open_position = False
                                    logging.info("Total profit is {} euros.\n".format(Profit))
                                elif SellChange <= -profit_margin:
                                    Loss = capital * SellChange
                                    logging.info("{} {} sold with loss of {} euros.".format(quantity, Symbol, Loss))
                                    Profit = StrategyData["Profit"].iloc[-1] + Loss
                                    open_position = False
                                    logging.info("Total profit is {} euros.\n".format(Profit))
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

def Plot(Symbols, lookback, event_queue_plot, event_queue_data, time_end):
    sql_engine = sqlalchemy.create_engine("sqlite:///Data.db")
    plt.style.use("seaborn-dark")
    mpl.rcParams['toolbar'] = 'None' 
    for param in ['figure.facecolor', 'axes.facecolor', 'savefig.facecolor']:
        plt.rcParams[param] = '#212946'  # bluish dark grey
    for param in ['text.color', 'axes.labelcolor', 'xtick.color', 'ytick.color']:
        plt.rcParams[param] = '0.9'  # very light grey 
    fig, ax = plt.subplots(2, len(Symbols), num="Kraken", figsize=(16,16))
    plt.ion()
    plt.show(block=False)
    while True:
        try:
            if event_queue_plot.get() == 1:
                StrategyData = pd.read_sql_table("Strategy", sql_engine)
                if len(StrategyData) == 0:
                    open_position = False
                    Profit = 0
                else:
                    open_position = StrategyData.Open_position.iloc[-1]
                    Profit = StrategyData.Profit.iloc[-1]
                plt.suptitle("Total Profit is: {:.2f} euros".format(Profit), fontsize = 20, fontweight = "bold")
                i=0
                for Symbol in Symbols:
                    if open_position == True:
                        if StrategyData.Symbol.iloc[-1] == StrategyData.Symbol.iloc[-lookback] and StrategyData.Symbol.iloc[-1]==Symbol:
                            Data = pd.read_sql_table(Symbol, sql_engine)
                            ax[0, i].cla()
                            ax[1, i].cla()
                            ax[0, i].grid(color='#2A3459')
                            ax[1, i].grid(color='#2A3459')
                            if Data.last_valid_index() >= lookback*10:
                                x = Data["Time"].iloc[-lookback*10:]
                                y = Data["Price"].iloc[-lookback*10:]
                                Startprice = y.iloc[-lookback*10]
                                Endprice = y.iloc[-1]
                                Change = (Endprice / Startprice) * 100 - 100
                                if Change >= 0:
                                    ax[0, i].plot(x, y, color='#39FF14', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#39FF14')
                                else:
                                    ax[0, i].plot(x, y, color='#B92E34', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#B92E34')
                            else:
                                x = Data["Time"]
                                y = Data["Price"]
                                Startprice = y.iloc[-lookback]
                                Endprice = y.iloc[-1]
                                Change = (Endprice / Startprice) * 100 - 100
                                if Change >= 0:
                                    ax[0, i].plot(x, y, color='#39FF14', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#39FF14')
                                else:
                                    ax[0, i].plot(x, y, color='#B92E34', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#B92E34')
                            ax[0, i].axhline(y=StrategyData["BuyPrice"].iloc[-1], color = '#F5D300', linestyle = '--', label = "BuyPrice")
                            ax[0, i].axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                            ax[0, i].legend()
                            ax[0, i].set_title(Symbol+" price.")
                            ax[0, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                            ax[0, i].tick_params('x', labelrotation = 45)
                            x = StrategyData["Time"].iloc[-lookback:]
                            y = StrategyData["Price"].iloc[-lookback:]
                            ax[1, i].plot(x, y, color='#08F7FE', label="Price")
                            ax[1, i].plot(x, StrategyData["SellPriceHigh"].iloc[-lookback:], color = '#00ff41', linestyle = '--', label = "SellPriceHigh")
                            ax[1, i].plot(x, StrategyData["SellPriceLow"].iloc[-lookback:], color = '#B92E34', linestyle = '--', label = "SellPriceLow")
                            ax[1, i].plot(x, StrategyData["TrackPrice"].iloc[-lookback:], color = "orange", linestyle = '--', label = "TrackPrice")
                            ax[1, i].axhline(y=StrategyData["BuyPrice"].iloc[-1], color = '#F5D300', linestyle = '--', label = "BuyPrice")
                            ax[1, i].axis([min(x), max(x), StrategyData["SellPriceLow"].iloc[-1]-StrategyData["Price"].iloc[-lookback:].mean()/2000, StrategyData["SellPriceHigh"].iloc[-1]+StrategyData["Price"].iloc[-lookback:].mean()/2000])
                            ax[1, i].legend()
                            ax[1, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                            ax[1, i].tick_params('x', labelrotation = 45)
                            plt.draw()
                            plt.pause(0.001)
                    elif open_position == False:
                        Data = pd.read_sql_table(Symbol, sql_engine)
                        ax[0, i].cla()
                        ax[1, i].cla()
                        ax[0, i].grid(color='#2A3459')
                        ax[1, i].grid(color='#2A3459')
                        if Data.Price.last_valid_index() >= lookback:
                            NewData = Data.iloc[-lookback:]
                            x = NewData["Time"]
                            y = NewData["Price"]
                            ax[1, i].plot(x, y, color='#08F7FE', label="Price")
                            ax[1, i].axhline(y=NewData["BuyPrice"].iloc[-1], color = '#F5D300', linestyle = '--', label = "BuyPrice")
                            ax[1, i].axis([min(x), max(x), NewData["Price"].min()-NewData["Price"].mean()/2000, NewData["BuyPrice"].iloc[-1]+NewData["Price"].mean()/2000])
                            ax[1, i].legend()
                            ax[1, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                            ax[1, i].tick_params('x', labelrotation = 45)
                            plt.draw()
                            plt.pause(0.001)

                        if Data.Price.last_valid_index() >= 2:
                            if Data.last_valid_index() >= lookback*10:
                                x = Data["Time"].iloc[-lookback*10:]
                                y = Data["Price"].iloc[-lookback*10:]
                                Startprice = y.iloc[-lookback*10]
                                Endprice = y.iloc[-1]
                                Change = (Endprice / Startprice) * 100 - 100
                                if Change >= 0:
                                    ax[0, i].plot(x, y, color='#39FF14', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#39FF14')
                                else:
                                    ax[0, i].plot(x, y, color='#B92E34', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#B92E34')
                            else:
                                x = Data["Time"]
                                y = Data["Price"]
                                Startprice = y.iloc[0]
                                Endprice = y.iloc[-1]
                                Change = (Endprice / Startprice) * 100 - 100
                                if Change >= 0:
                                    ax[0, i].plot(x, y, color='#39FF14', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#39FF14')
                                else:
                                    ax[0, i].plot(x, y, color='#B92E34', label="Price")
                                    ax[0, i].text(min(x), y.min()-y.mean()/2000, "{:.2f}%".format(Change), color='#B92E34')
                            ax[0, i].axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                            ax[0, i].legend()
                            ax[0, i].set_title(Symbol+" price.")
                            ax[0, i].xaxis.set_major_formatter(mdates.DateFormatter('%I:%M:%S'))
                            ax[0, i].tick_params('x', labelrotation = 45)
                            plt.draw()
                            plt.pause(0.001)

                    i=i+1 
                time_end.put(round(datetime.now(timezone.utc).astimezone().timestamp() * 1000))
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
    TRAILING = os.getenv("TRAILING", 'False').lower() in ('true', '1', 't')


    event_queue_data = Queue()
    event_queue_strat = Queue()
    event_queue_plot = Queue()
    time_end = Queue(maxsize=1)
    
    event_queue_data.put(1)
    time_end.put(round(datetime.now(timezone.utc).astimezone().timestamp() * 1000))
    Thread(target=load_data, args=(SYMBOLS, event_queue_data, event_queue_strat, time_end)).start()
    Thread(target=strategyChange, args=(SYMBOLS, ENTRY, CAPITAL, PROFIT_MARGIN, LOOKBACK, event_queue_strat, event_queue_plot)).start()
    Plot(SYMBOLS, LOOKBACK, event_queue_plot, event_queue_data, time_end)
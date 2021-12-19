import krakenex
import pandas as pd
import os
import sqlalchemy
import json
from time import sleep
from datetime import datetime
from dotenv import load_dotenv
from threading import Thread
from pykrakenapi import KrakenAPI
import os
os.environ['MPLCONFIGDIR'] = os.getcwd() + "/configs/"
import matplotlib.pyplot as plt
import logging
import logging.config

def load_data(Symbols):
    for Symbol in Symbols:
        if os.path.exists(Symbol+"stream.db"):
            os.remove(Symbol+"stream.db")
    while True:
        try:
            for Symbol in Symbols:
                sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

                Symbol_time_start = round(datetime.utcnow().timestamp() * 1000)
                
                Data = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'BuyPrice', 'SellPriceHigh', 'SellPriceLow', 'Open_position'])
                
                Symboldata = kraken.get_ticker_information(Symbol)
                Data = Data.append({"Symbol" : Symbol, "Price" : Symboldata['a'][0][0], "Time" : pd.to_datetime(Symbol_time_start, unit = 'ms'), "BuyPrice": 0, "SellPriceHigh": 0, "SellPriceLow": 0, "Open_position": False}, ignore_index = True)
                Data.Price = Data.Price.astype(float)
                Data.to_sql(Symbol, sql_engine, if_exists="append", index=False)

                Symbol_time_end = round(datetime.utcnow().timestamp() * 1000)
                Symbol_time_diff = Symbol_time_end - Symbol_time_start
                if Symbol_time_diff < 1000:
                    wait_time = (1000 - Symbol_time_diff)/1000 + 0.01
                    sleep(wait_time)
        except Exception as e:
            logging.info("Unable to retrieve data\n{}".format(e))
            break
        except KeyboardInterrupt:
            break

def plot(Symbols, lookback):
    while True:
        try:
            for Symbol in Symbols:
                sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

                plt.ion()
                plt.show(block=False)

                Data = pd.read_sql(Symbol, sql_engine)

                if Data.Price.last_valid_index() >= lookback:
                    NewData = Data.iloc[-lookback:]
                    x = NewData["Time"]
                    y = NewData["Price"]
                    plt.axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                    plt.plot(x,y, color='blue')
                    print(Data.Open_position.iloc[-1])
                    if Data.Open_position.iloc[-1] == True:
                        plt.axhline(y=Data["SellPriceHigh"].iloc[-1], color = 'green')
                        plt.axhline(y=Data["SellPriceLow"].iloc[-1], color = 'red')
                        plt.axhline(y=Data["BuyPrice"].iloc[-1], color = "black")
                    else:
                        print(Data["BuyPrice"].iloc[-1])
                        plt.axhline(y=Data["BuyPrice"].iloc[-1], color = 'orange')
                    plt.gcf().autofmt_xdate()
                    plt.title(Symbol+" price.")
                    plt.draw()
                    plt.pause(0.001)

                else:
                    x = Data["Time"]
                    y = Data["Price"]
                    plt.axis([min(x), max(x), Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000])
                    plt.plot(x,y, color='blue')
                    plt.gcf().autofmt_xdate()
                    plt.title(Symbol+" price.")
                    plt.draw()
                    plt.pause(0.001)
            sleep(1)
        except Exception as e:
            logging.error(e)
            break
        except KeyboardInterrupt:
            break

def strategyChange(Symbols, entry, capital, lookback):
    logging.info("Buying for {} euros.".format(capital))
    logging.info("Selling when change is greater than {}%.".format(entry*100))
    while True:
        for Symbol in Symbols:
            sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

            try:
                Data = pd.read_sql(Symbol, sql_engine)

                if Data.Price.last_valid_index() >= lookback:
                    open_position = Data.Open_position.iloc[-1]

                    StartPrice = Data.Price.iloc[-lookback]
                    LastPrice = Data.Price.iloc[-1]

                    BuyChange = LastPrice / StartPrice - 1

                    if not open_position:
                        Data.BuyPrice.iloc[-1] = (entry+1) * LastPrice
                        if BuyChange > entry:
                            #order = kraken.add_standard_order(pair=Symbol, type='buy', ordertype='limit', volume='0.007', price=qty, validate=False)
                            #print(order)
                            quantity = capital/LastPrice
                            BuyPrice = LastPrice

                            logging.info("{} {} bought for: {}".format(quantity, Symbol, LastPrice))
                            bought_time = round(datetime.utcnow().timestamp() * 1000)
                            
                            Data.BuyPrice.iloc[-1] = BuyPrice
                            Data.Open_position.iloc[-1] = True
                        else:
                            logging.info("Not buying {} yet.".format(Symbol))

                    if open_position:
                        #sincebuy = Data.loc[Data.Time > pd.to_datetime(order['TransactTime'], unit = "ms")]
                        sincebuy = Data.loc[Data.Time > pd.to_datetime(bought_time, unit = "ms")]
                        if len(sincebuy) > 1:
                            SellChange = BuyPrice / LastPrice - 1
                            Data.SellPriceHigh.iloc[-1] = 1.0015 * BuyPrice
                            Data.SellPriceHigh.iloc[-1] = 0.9985 * BuyPrice
                            if SellChange > 0.0015:
                                #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                                #print(order)
                                SellPrice = LastPrice
                                Profit = SellPrice - BuyPrice
                                logging.info("{} sold with profit for: {}".format(Symbol, Profit))
                                Data.Open_position.iloc[-1] = False

                            if SellChange < -0.0015:
                                SellPrice = LastPrice
                                Loss = SellPrice - BuyPrice
                                logging.info("{} sold with loss for: {}".format(Symbol, Loss))
                                Data.Open_position.iloc[-1] = False
                        Data.BuyPrice.iloc[-1] = BuyPrice
                sleep(1)
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

    logging.info("Tracking assets: {}\n".format(SYMBOLS))

    Thread(target=load_data, args=(SYMBOLS,)).start()
    sleep(2)
    Thread(target=strategyChange, args=(SYMBOLS, 0.005, 1000, 60)).start()
    plot(SYMBOLS, 60)
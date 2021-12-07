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
import logging

def load_data(Symbols):
    for Symbol in Symbols:
        if os.path.exists(Symbol+"stream.db"):
            os.remove(Symbol+"stream.db")
    while True:
        try:
            for Symbol in Symbols:
                sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

                Symbol_time_start = round(datetime.utcnow().timestamp() * 1000)
                
                Data = pd.DataFrame(columns = ['Symbol', 'Price', 'Time', 'Trackprice', 'Open_position'])
                
                Symboldata = kraken.get_ticker_information(Symbol)
                Data = Data.append({"Symbol" : Symbol, "Price" : Symboldata['a'][0][0], "Time" : pd.to_datetime(Symbol_time_start, unit = 'ms'), "Trackprice": 0, "Open_position": False}, ignore_index = True)
                Data.Price = Data.Price.astype(float)
                logging.info(Data)
                logging.info("\n")
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
            logging.info("Shutting down...")
            break

def strategy(Symbol, entry, lookback, qty, open_position = False):
    Data = pd.read_sql(Symbol, sql_engine)
    logging.info(Data)
    print(lookback)
    lookbackperiod = Data.iloc[-lookback:]
    cumret = (lookbackperiod.Price.pct_change() + 1).cumprod() - 1
    if not open_position:
        if cumret[cumret.last_valid_index()] > entry:
            #order = kraken.add_standard_order(pair=Symbol, type='buy', ordertype='limit', volume='0.007', price=qty, validate=False)
            #print(order)
            print("Bought for: {}".format(Data.Price.iloc[-1:]))
            bought_time = round(datetime.utcnow().timestamp() * 1000)
            open_position = True
        else:
            logging.info("Not buying {} yet.".format(Symbol))

    
    if open_position:
        #sincebuy = Data.loc[Data.Time > pd.to_datetime(order['TransactTime'], unit = "ms")]
        sincebuy = Data.loc[Data.Time > bought_time]
        if len(sincebuy) > 1:
            sincebuyret = (sincebuy.Price.pct_change() + 1).cumprod() - 1
            last_entry = sincebuyret[sincebuyret.last_valid_index()]
            if last_entry > 0.0015 or last_entry < -0.0015:
                #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                #print(order)
                print("Sold for: {}".format(Data.Price.iloc[-1:]))
                open_position = False

def strategyChange(Symbols, entry, quantity, lookback, open_position=False):
    while True:
        for Symbol in Symbols:
            sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")
            try:
                Symbol_time_start = round(datetime.utcnow().timestamp() * 1000)

                Data = pd.read_sql(Symbol, sql_engine)

                if Data.Price.last_valid_index() >= lookback:
                    StartPrice = Data.Price.iloc[-lookback]
                    EndPrice = Data.Price.iloc[-1]

                    Change = EndPrice / StartPrice - 1

                    if not open_position:
                        if Change > entry:
                            #order = kraken.add_standard_order(pair=Symbol, type='buy', ordertype='limit', volume='0.007', price=qty, validate=False)
                            #print(order)
                            logging.info("{} bought for: {}".format(Symbol, Data.Price.iloc[-1]))
                            bought_time = round(datetime.utcnow().timestamp() * 1000)
                            open_position = True
                        else:
                            logging.info("Not buying {} yet.\n".format(Symbol))

                    if open_position:
                        #sincebuy = Data.loc[Data.Time > pd.to_datetime(order['TransactTime'], unit = "ms")]
                        sincebuy = Data.loc[Data.Time > pd.to_datetime(bought_time, unit = "ms")]
                        if len(sincebuy) > 1:

                            StartPrice = Data.Price.iloc[sincebuy]
                            EndPrice = Data.Price.iloc[-1]

                            Change = StartPrice / EndPrice - 1

                            if Change > 0.0015:
                                #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                                #print(order)
                                print("Sold with profit for: {}".format(EndPrice))
                                open_position = False

                            if Change < -0.0015:
                                logging.info("Sold with loss for: {}".format(EndPrice))
                                open_position = False
                
                Symbol_time_end = round(datetime.utcnow().timestamp() * 1000)
                Symbol_time_diff = Symbol_time_end - Symbol_time_start
                if Symbol_time_diff < 1000:    
                    wait_time = (1000 - Symbol_time_diff)/1000 + 0.01
                    sleep(wait_time)
            
            except Exception as e:
                logging.info("Unable to perform strategy\n{}".format(e))
                break
            except KeyboardInterrupt:
                logging.info("Shutting down...")
                break

if __name__ == "__main__":
    api = krakenex.API()
    api.load_key('kraken_api_key.txt')
    kraken = KrakenAPI(api)

    logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S', level=logging.DEBUG)

    load_dotenv(dotenv_path="kraken.env")
    SYMBOLS = json.loads(os.getenv("SYMBOLS"))

    logging.info("Tracking assets: {}\n".format(SYMBOLS))

    Thread(target=load_data, args=(SYMBOLS,)).start()
    sleep(1)
    Thread(target=strategyChange, args=(SYMBOLS, 0.1, 0.1, 60)).start()

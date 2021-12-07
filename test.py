import krakenex
import pandas as pd
import os
import sqlalchemy
import json
import logging
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from time import sleep
from datetime import datetime
from dotenv import load_dotenv
from threading import Thread
from pykrakenapi import KrakenAPI


logging.basicConfig(format='%(asctime)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S', level=logging.DEBUG)

Symbol = "ETHUSDT"
sql_engine = sqlalchemy.create_engine("sqlite:///"+Symbol+"stream.db")

def Plots(i):
    ax.cla()
    ax1.cla()
    Data = pd.read_sql(Symbol, sql_engine)
    lookback=60
    Data.plot(x="Time", y="Price", ylim=(Data["Price"].min()-Data["Price"].mean()/2000, Data["Price"].max()+Data["Price"].mean()/2000), xlim=(Data["Time"].min(), Data["Time"].max()), title=Symbol+" price.", ylabel="Price", xlabel="Time", ax=ax)
    if Data.Price.last_valid_index() >= lookback:
        NewData = Data.iloc[-lookback:]
        NewData.plot(x="Time", y="Price", ylim=(NewData["Price"].min()-NewData["Price"].mean()/2000, NewData["Price"].max()+NewData["Price"].mean()/2000), xlim=(NewData["Time"].min(), NewData["Time"].max()), ylabel="Price", xlabel="Time", ax=ax1)
    if Data.Open_position.iloc[-1] == True:
        ax.plot(y=Data["Trackprice"].iloc[-1])
        ax1.plot(y=Data["Trackprice"].iloc[-1])

def strategyChange(Symbol, entry, capital, lookback):
    while True:
        Data = pd.read_sql(Symbol, sql_engine)

        if Data.Price.last_valid_index() >= lookback:
            open_position = Data.Open_position.iloc[-1]

            StartPrice = Data.Price.iloc[-lookback]
            LastPrice = Data.Price.iloc[-1]

            BuyChange = LastPrice / StartPrice - 1

            if not open_position:
                if BuyChange > entry:
                    #order = kraken.add_standard_order(pair=Symbol, type='buy', ordertype='limit', volume='0.007', price=qty, validate=False)
                    #print(order)
                    quantity = capital/LastPrice
                    BuyPrice = LastPrice

                    logging.info("{} {} bought for: {}".format(quantity, Symbol, LastPrice))
                    bought_time = round(datetime.utcnow().timestamp() * 1000)
                    
                    Data.Trackprice.iloc[-1] = BuyPrice
                    Data.Open_position.iloc[-1] = True
                else:
                    logging.info("Not buying {} yet.".format(Symbol))

            if open_position:
                #sincebuy = Data.loc[Data.Time > pd.to_datetime(order['TransactTime'], unit = "ms")]
                sincebuy = Data.loc[Data.Time > pd.to_datetime(bought_time, unit = "ms")]
                if len(sincebuy) > 1:
                    TrackPrice = Data.Trackprice.iloc[-1]
                    SellChange = TrackPrice / LastPrice - 1

                    if LastPrice > TrackPrice:
                        Data.Trackprice.iloc[-1] = LastPrice
                        SellChange = TrackPrice / LastPrice - 1
                        if SellChange > 0.0015:
                            #order = kraken.add_standard_order(pair=Symbol, type='sell', ordertype='limit', volume='0.007', price='qty', validate=False)
                            #print(order)
                            SellPrice = LastPrice
                            Profit = SellPrice - 
                            print("{} {} sold with profit for: {}".format(LastPrice))
                            Data.Open_position.iloc[-1] = False

                    if SellChange < -0.0015:
                        logging.info("Sold with loss for: {}".format(LastPrice))
                        Data.Open_position.iloc[-1] = False
                        
fig, (ax, ax1) = plt.subplots(2, 1, figsize=(8,6), facecolor='#DEDEDE', gridspec_kw={'height_ratios': [1, 3]})
ax.set_facecolor('#DEDEDE')
ax1.set_facecolor('#DEDEDE')
fig.tight_layout()
ani = FuncAnimation(fig, Plots, interval=1000)

plt.show()
strategyChange(Symbol, 0.01, 100, 60)


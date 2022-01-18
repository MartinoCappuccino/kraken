# Kraken Trading Bot

This is the kraken trading bot, created to analyze the market, buy the dip and sell the peak.
You will need the API key from your kraken account.

## Install python packages

First we will have to install some python dependencies:

~~~console
pip3 install krakenex pykrakenapi sqlalchemy pandas matplotlib python-dotenv
~~~

## Setup of the kraken trading bot

We will start by cloning the kraken repository:

~~~console
cd /home/martijn/projects/
git clone https://github.com/MartinoCappuccino/kraken.git
~~~

Create a file called kraken_api_key.txt and put your API key into this file:

~~~console
cd /home/martijn/projects/kraken
touch kraken_api_key.txt
~~~

Now we can initialize the service file for this service by:

~~~console
sudo cp /home/machytech/projects/kraken/kraken.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable kraken.service
sudo systemctl start kraken.service
~~~

To check the status use:

~~~console
sudo systemctl status kraken.service
~~~

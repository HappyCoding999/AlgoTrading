import datetime  
import backtrader as bt
from angelbt import ANGELStore
from datetime import datetime, timedelta

from angelbt import ZerodhaFeed
class VolumeWeightedAveragePrice(bt.Indicator):
    plotinfo = dict(subplot=False)
    params = (('period', 30), )
    alias = ('VWAP', 'VolumeWeightedAveragePrice',)
    lines = ('vwap',)
    plotlines = dict(VWAP=dict(alpha=0.50, linestyle='-.', linewidth=2.0))

    def __init__(self):
        cumvol = bt.ind.SumN(self.data.volume, period = self.p.period)
        typprice = ((self.data.close + self.data.high + self.data.low)/3) * self.data.volume
        cumtypprice = bt.ind.SumN(typprice, period=self.p.period)
        self.lines[0] = cumtypprice / cumvol
        super(VolumeWeightedAveragePrice, self).__init__()

class OptionStrategyEma(bt.Strategy):
    
    params = dict(
        pRsi = 14,
        pRsiLevel = 60,
        pVwap = 14,
        pSma = 20,
        stop_loss=10,
        pRr =3,
        pSmaSL=10,
        multiple = 2,
        volumerate=1.5,
        initsize = 1
    )
    lines = ('vwap',)
    def __init__(self):
        self.countloss = 0
        self.rsi = bt.indicators.RelativeStrengthIndex(period=self.p.pRsi)
        self.sma20Oi = bt.ind.SMA(self.datas[0].oi,period=self.p.pSma, plot=True,subplot=True)
        self.sma20Volume= bt.ind.SMA(self.datas[0].volume,period=self.p.pSma, plot=False)
        self.vwap =  VolumeWeightedAveragePrice(period=self.p.pVwap)
        self.openi = self.datas[0].oi
        self.smalow = bt.ind.SMA(self.datas[0].low,period=self.p.pSmaSL, plot=True)
        self.backtest = True
        self.bought = False
        self.order = None

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def notify_order(self, order):
        #Check if order has been completed
        if order.status in [order.Completed]:
            if order.isbuy(): # Long
                self.log(
                    'LONG EXECUTED Ref: %d,Size %.4f, Price: %.4f, Cost: %.2f, Comm: %.2f' %
                    (order.ref,
                     order.executed.size,
                     order.executed.price,
                     order.executed.value,
                     order.executed.comm)
                    )
                
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                
            else: # Short
                self.log(
                    'SHORT EXECUTED Ref: %d, Size %.4f, Price: %.4f, Cost: %.2f, Comm: %.2f' %
                    (order.ref,
                     order.executed.size,
                     order.executed.price,
                     order.executed.value,
                     order.executed.comm)
                    )
                
                self.sell_price = order.executed.price
                self.sell_comm = order.executed.comm
                self.bought = False
                # Clean up the order list.
                #self.cancel(self.stop_order)
                #self.cancel(self.tp_order)
  
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Ref %03d : SL/TP Order Canceled/Margin/Rejected'
                     % (order.ref))

    def notify_trade(self, trade):
        if trade.justopened:
            self.log('Trade Opened  - Size {%.4f} @Price {%.4f}'
                    %(trade.size, trade.price))
        elif trade.isclosed:
            if(trade.pnlcomm>0):
                self.countloss = 0
            else:
                self.countloss = self.countloss +1
            self.log('Trade Closed  - Profit {%.4f}' % (trade.pnlcomm))

        else:  # trade updated
            self.log('Trade Updated - Size %.4f @Price {%.4f}' % (trade.size, trade.price))    
    
    def notify_data(self, data, status, *args, **kwargs):
        dn = data._name
        dt = datetime.now()
        msg = 'Data Status: {}, Order Status: {}'.format(data._getstatusname(status), status)
        print(dt, dn, msg)
        if data._getstatusname(status) == 'LIVE':
            self.live_data = True
        else:
            self.live_data = False

    def next(self):
        # 14rsi(option price) > 60  => 14 ?
        #  option price > 14 vwap  => 14 ? 
        #  20sma(open interest)>open interest => 20 ? 
        #  volume>20sma(volume) => 20 ?
        # sl is privious vwap-10
        if self.live_data:
            cash, value = self.broker.get_balance()
        else:
            cash = 'NA'
        for data in self.datas:
            print('{} - {} | Cash {} | O: {} H: {} L: {} C: {} V:{}  OI:{} SMAVOLUME:{} SMALOW:{} RSI:{} VWAP:{} SMAOI:{}'.format( \
                data.datetime.datetime(),data._name, cash, \
                data.open[0], data.high[0], data.low[0], data.close[0], data.volume[0],data.oi[0], \
                self.sma20Volume[0],self.smalow[0],self.rsi[0],self.vwap[0],self.sma20Oi[0]))
        self.buysignal  = self.rsi[0]>self.p.pRsiLevel \
            and self.datas[0].close[0]>self.vwap[0] \
            and self.sma20Oi[0] > self.datas[0].oi[0] \
            and self.datas[0].volume[0]>self.sma20Volume[0] * self.p.volumerate
        if (self.live_data or self.backtest) and not self.bought:
            if self.buysignal:  # if fast crosses slow to the upside
                lotsize = self.p.initsize*pow(self.p.multiple,self.countloss)
                self.order = self.buy(size=lotsize)  # enter long
                self.bought = True
                
        if self.bought :
            if(self.datas[0].close[0]<self.smalow[0]):
                lotsize = self.p.initsize*pow(self.p.multiple,self.countloss)
                self.sell_order = self.sell(size=lotsize)  # enter short

cerebro = bt.Cerebro(quicknotify=True) 
cerebro.addstrategy(OptionStrategyEma)  # Add the trading strategy
config = {'api_key':"Pj61Oa6u",
        'client_id':"P193991",
        'client_pw':"mapatel123"
        }

backtest = True
if backtest == False:
    store = ANGELStore(config=config,retries=5)
    broker = store.getbroker()
    cerebro.setbroker(broker)
    hist_start_date = datetime.utcnow() - timedelta(minutes=60*24*3)
    data = store.getdata(dataname='NIFTY21NOV18000PE', name="NIFTY",
                        timeframe=bt.TimeFrame.Minutes, fromdate=hist_start_date,
                        compression=5)
    cerebro.adddata(data)

if backtest :
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(ZerodhaFeed(
                                dataname='NIFTY21N1818000CE', name="NIFTY21N1818000CE",
                                timeframe=bt.TimeFrame.Minutes,compression=5,
                                fromdate=datetime(2021, 11,3, 0, 0),
                                todate=datetime(2021, 11, 12, 0, 0),
                                config=config))
cerebro.run()  # run it all
if backtest :
    cerebro.plot(path = 'savefig.png',width=16, height=9,dpi=100) #cerebro.plot()  # and plot it with a single command


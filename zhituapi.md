# 智兔API配置（主要数据源）
# 获取地址：https://api.zhituapi.cn
ZHITU_API_BASE_URL=https://api.zhituapi.cn
ZHITU_API_TOKEN=your_zhitu_api_token_here

股票列表
API地址：https://api.zhituapi.cn/hs/list/all?token=token证书

描述：获取基础的股票代码和名称，用于后续接口的参数传入。

更新频率：每日16:20

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次
字段名称	数据类型	字段说明
dm	string	股票代码，如：000001
mc	string	股票名称，如：平安银行
jys	string	交易所，"sh"表示上证，"sz"表示深证

涨停股池
API地址：https://api.zhituapi.cn/hs/pool/ztgc/交易日期?token=token证书

描述：根据日期（格式yyyy-MM-dd，从2019-11-28开始到现在的每个交易日）作为参数，得到每天的涨停股票列表，根据封板时间升序。

更新频率：交易时间段每10分钟

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次
字段名称	数据类型	字段说明
dm	string	代码
mc	string	名称
p	number	价格（元）
zf	number	涨幅（%）
cje	number	成交额（元）
lt	number	流通市值（元）
zsz	number	总市值（元）
hs	number	换手率（%）
lbc	number	连板数
fbt	string	首次封板时间（HH:mm:ss）
lbt	string	最后封板时间（HH:mm:ss）
zj	number	封板资金（元）
zbc	number	炸板次数
tj	string	涨停统计（x天/y板）

跌停股池
API地址：https://api.zhituapi.cn/hs/pool/dtgc/交易日期?token=token证书

描述：根据日期（格式yyyy-MM-dd，从2019-11-28开始到现在的每个交易日）作为参数，得到每天的跌停股票列表，根据封单资金升序。

更新频率：交易时间段每10分钟

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次
字段名称	数据类型	字段说明
dm	string	代码
mc	string	名称
p	number	价格（元）
zf	number	跌幅（%）
cje	number	成交额（元）
lt	number	流通市值（元）
zsz	number	总市值（元）
pe	number	动态市盈率
hs	number	换手率（%）
lbc	number	连续跌停次数
lbt	string	最后封板时间（HH:mm:ss）
zj	number	封单资金（元）
fba	number	板上成交额（元）
zbc	number	开板次数


强势股池
API地址：https://api.zhituapi.cn/hs/pool/qsgc/交易日期?token=token证书

描述：根据日期（格式yyyy-MM-dd，从2019-11-28开始到现在的每个交易日）作为参数，得到每天的强势股票列表，根据涨幅倒序。

更新频率：交易时间段每10分钟

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
dm	string	代码
mc	string	名称
p	number	价格（元）
ztp	number	涨停价（元）
zf	number	涨幅（%）
cje	number	成交额（元）
lt	number	流通市值（元）
zsz	number	总市值（元）
zs	number	涨速（%）
nh	number	是否新高（0：否，1：是）
lb	number	量比
hs	number	换手率（%）
tj	string	涨停统计（x天/y板）

实时交易（公开数据源）
API地址：https://api.zhituapi.cn/hs/real/ssjy/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取实时交易数据（您可以理解为日线的最新数据）。

更新频率：交易时间段每1分钟

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
fm	number	五分钟涨跌幅（%）
h	number	最高价（元）
hs	number	换手（%）
lb	number	量比（%）
l	number	最低价（元）
lt	number	流通市值（元）
o	number	开盘价（元）
pe	number	市盈率（动态，总市值除以预估全年净利润，例如当前公布一季度净利润1000万，则预估全年净利润4000万）
pc	number	涨跌幅（%）
p	number	当前价格（元）
sz	number	总市值（元）
cje	number	成交额（元）
ud	number	涨跌额（元）
v	number	成交量（手）
yc	number	昨日收盘价（元）
zf	number	振幅（%）
zs	number	涨速（%）
sjl	number	市净率
zdf60	number	60日涨跌幅（%）
zdfnc	number	年初至今涨跌幅（%）
t	string	更新时间yyyy-MM-ddHH:mm:ss

当天逐笔交易
API地址：https://api.zhituapi.cn/hs/real/zbjy/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取当天逐笔交易数据，按时间倒序。

更新频率：21:00

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
d	string	数据归属日期（yyyy-MM-dd）
t	string	时间（HH:mm:dd）
v	number	成交量（股）
p	number	成交价
ts	number	交易方向（0：中性盘，1：买入，2：卖出）


实时交易（全部 | 公开数据）
API地址：https://api.zhituapi.cn/hs/public/realall?token=token证书

描述：一次性获取《股票列表》中所有股票的实时交易数据（您可以理解为日线的最新数据），该接口仅限至尊版和包年版token使用且限制每分钟请求1次。

更新频率：交易时间段每1分钟

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
fm	number	五分钟涨跌幅（%）
h	number	最高价（元）
hs	number	换手（%）
lb	number	量比（%）
l	number	最低价（元）
lt	number	流通市值（元）
o	number	开盘价（元）
pe	number	市盈率（动态，总市值除以预估全年净利润，例如当前公布一季度净利润1000万，则预估全年净利润4000万）
pc	number	涨跌幅（%）
p	number	当前价格（元）
sz	number	总市值（元）
cje	number	成交额（元）
ud	number	涨跌额（元）
v	number	成交量（手）
yc	number	昨日收盘价（元）
zf	number	振幅（%）
zs	number	涨速（%）
sjl	number	市净率
zdf60	number	60日涨跌幅（%）
zdfnc	number	年初至今涨跌幅（%）
t	string	更新时间yyyy-MM-ddHH:mm:ss

实时交易（多选 | 公开数据）
API地址：https://api.zhituapi.cn/hs/public/ssjymore?stock_codes=股票1代码,股票2代码,……,股票20代码&token=token证书

描述：根据《股票列表》得到的股票代码指定不超过20支股票代码获取实时交易数据（您可以理解为日线的最新数据），该接口仅限至尊版和包年版token使用。

更新频率：交易时间段每1分钟

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
fm	number	五分钟涨跌幅（%）
h	number	最高价（元）
hs	number	换手（%）
lb	number	量比（%）
l	number	最低价（元）
lt	number	流通市值（元）
o	number	开盘价（元）
pe	number	市盈率（动态，总市值除以预估全年净利润，例如当前公布一季度净利润1000万，则预估全年净利润4000万）
pc	number	涨跌幅（%）
p	number	当前价格（元）
sz	number	总市值（元）
cje	number	成交额（元）
ud	number	涨跌额（元）
v	number	成交量（手）
yc	number	昨日收盘价（元）
zf	number	振幅（%）
zs	number	涨速（%）
sjl	number	市净率
zdf60	number	60日涨跌幅（%）
zdfnc	number	年初至今涨跌幅（%）
t	string	更新时间yyyy-MM-ddHH:mm:ss


实时交易（券商数据源）
API地址：https://api.zhituapi.cn/hs/real/time/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取实时交易数据（您可以理解为日线的最新数据）。

更新频率：实时

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
p	number	最新价
o	number	开盘价
h	number	最高价
l	number	最低价
yc	number	前收盘价
cje	number	成交总额
v	number	成交总量
pv	number	原始成交总量
t	string	更新时间
ud	float	涨跌额
pc	float	涨跌幅
zf	float	振幅
t	string	更新时间
pe	number	市盈率
tr	number	换手率
pb_ratio	number	市净率
tv	number	成交量


买卖五档盘口(新增)
API地址：https://api.zhituapi.cn/hs/real/five/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取实时买卖五档盘口数据。

更新频率：实时

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
ps	number	委卖价
pb	number	委买价
vs	number	委卖量
vb	number	委买量
t	string	更新时间

实时交易（全部 | 券商数据）
API地址：https://api.zhituapi.cn/hs/custom/realall?token=token证书

描述：一次性获取《股票列表》中所有股票的实时交易数据（您可以理解为日线的最新数据），该接口仅限至尊版和包年版证书使用且限制每分钟请求1次。

更新频率：实时

请求频率限制：1分钟1次

字段名称	数据类型	字段说明
dm	string	股票代码
p	number	最新价
o	number	开盘价
h	number	最高价
l	number	最低价
yc	number	前收盘价
cje	number	成交总额
v	number	成交总量
pv	number	原始成交总量
ud	float	涨跌额
pc	float	涨跌幅
zf	float	振幅
t	string	更新时间
pe	number	市盈率
tr	number	换手率
pb_ratio	number	市净率
tv	number	成交量

实时交易（多选 | 券商数据）
API地址：http://api.zhituapi.cn/hs/custom/ssjymore?token=token证书&tock_codes=股票代码1,股票代码2……股票代码20

描述：一次性获取《股票列表》中不超过20支股票的实时交易数据（您可以理解为日线的最新数据），该接口仅限至尊版和包年版token使用。

更新频率：实时

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
p	number	最新价
o	number	开盘价
h	number	最高价
l	number	最低价
yc	number	前收盘价
cje	number	成交总额
v	number	成交总量
pv	number	原始成交总量
t	string	更新时间
ud	float	涨跌额
pc	float	涨跌幅
zf	float	振幅
t	string	更新时间
pe	number	市盈率
tr	number	换手率
pb_ratio	number	市净率
tv	number	成交量


资金流向数据
API地址：https://api.zhituapi.cn/hs/history/transaction/股票代码?token=token证书&st=开始时间&et=结束时间&lt=最新条数

描述：根据《股票列表》得到的股票代码获取资金流向数据。开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'，不设置开始时间和结束时间则为全部历史数据。同时可以指定获取数据条数，例如指定lt=10，则获取最新的10条数据。下列字段中，特大单为成交金额大于或等于100万元或成交量大于或等于5000手，大单为成交金额大于或等于20万元或成交量大于或等于1000手，中单为成交金额大于或等于4万元或成交量大于或等于200手，其他为小单。

更新频率：每日21:30更新

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	int	交易时间
zmbzds	int	主买单总单数
zmszds	int	主卖单总单数
dddx	float	大单动向
zddy	float	涨跌动因
ddcf	float	大单差分
zmbzdszl	int	主买单总单数增量
zmszdszl	int	主卖单总单数增量
cjbszl	int	成交笔数增量
zmbtdcje	float	主买特大单成交额
zmbddcje	float	主买大单成交额
zmbzdcje	float	主买中单成交额
zmbxdcje	float	主买小单成交额
zmbljcje	float	主买累计成交额
zmstdcje	float	主卖特大单成交额
zmsddcje	float	主卖大单成交额
zmszdcje	float	主卖中单成交额
zmsxdcje	float	主卖小单成交额
zmsljcje	float	主卖累计成交额
bdmbtdcje	float	被动买特大单成交额
bdmbddcje	float	被动买大单成交额
bdmbzdcje	float	被动买中单成交额
bdmbxdcje	float	被动买小单成交额
bdmbljcje	float	被动买累计成交额
bdmstdcje	float	被动卖特大单成交额
bdmsddcje	float	被动卖大单成交额
bdmszdcje	float	被动卖中单成交额
bdmsxdcje	float	被动卖小单成交额
bdmsljcje	float	被动卖累计成交额
jlrcdcje	float	净流入超大单成交额
jlrddcje	float	净流入大单成交额
jlrzdcje	float	净流入中单成交额
jlrxdcje	float	净流入小单成交额
zmbtdcjl	int	主买特大单成交量
zmbddcjl	int	主买大单成交量
zmbzdcjl	int	主买中单成交量
zmbxdcjl	int	主买小单成交量
zmbljcjl	int	主买累计成交量
zmstdcjl	int	主卖特大单成交量
zmsddcjl	int	主卖大单成交量
zmszdcjl	int	主卖中单成交量
zmsxdcjl	int	主卖小单成交量
zmsljcjl	int	主卖累计成交量
bdmbtdcjl	int	被动买特大单成交量
bdmbddcjl	int	被动买大单成交量
bdmbzdcjl	int	被动买中单成交量
bdmbxdcjl	int	被动买小单成交量
bdmbljcjl	int	被动买累计成交量
bdmstdcjl	int	被动卖特大单成交量
bdmsddcjl	int	被动卖大单成交量
bdmszdcjl	int	被动卖中单成交量
bdmsxdcjl	int	被动卖小单成交量
bdmsljcjl	int	被动卖累计成交量
jlrcdcjl	int	净流入超大单成交量
jlrddcjl	int	净流入大单成交量
jlrzdcjl	int	净流入中单成交量
jlrxdcjl	int	净流入小单成交量
zmbtdcjzl	float	主买特大单成交额增量
zmbddcjzl	float	主买大单成交额增量
zmbzdcjzl	float	主买中单成交额增量
zmbxdcjzl	float	主买小单成交额增量
zmbljcjzl	float	主买累计成交额增量
zmstdcjzl	float	主卖特大单成交额增量
zmsddcjzl	float	主卖大单成交额增量
zmszdcjzl	float	主卖中单成交额增量
zmsxdcjzl	float	主卖小单成交额增量
zmsljcjzl	float	主卖累计成交额增量
bdmbtdcjzl	float	被动买特大单成交额增量
bdmbddcjzl	float	被动买大单成交额增量
bdmbzdcjzl	float	被动买中单成交额增量
bdmbxdcjzl	float	被动买小单成交额增量
bdmbljcjzl	float	被动买累计成交额增量
bdmstdcjzl	float	被动卖特大单成交额增量
bdmsddcjzl	float	被动卖大单成交额增量
bdmszdcjzl	float	被动卖中单成交额增量
bdmsxdcjzl	float	被动卖小单成交额增量
bdmsljcjzl	float	被动卖累计成交额增量
jlrcdcjzl	float	净流入超大单成交额增量
jlrddcjzl	float	净流入大单成交额增量
jlrzdcjzl	float	净流入中单成交额增量
jlrxdcjzl	float	净流入小单成交额增量
zmbtdcjzlv	int	主买特大单成交量增量
zmbddcjzlv	int	主买大单成交量增量
zmbzdcjzlv	int	主买中单成交量增量
zmbxdcjzlv	int	主买小单成交量增量
zmbljcjzlv	int	主买累计成交量增量
zmstdcjzlv	int	主卖特大单成交量增量
zmsddcjzlv	int	主卖大单成交量增量
zmszdcjzlv	int	主卖中单成交量增量
zmsxdcjzlv	int	主卖小单成交量增量
zmsljcjzlv	int	主卖累计成交量增量
bdmbtdcjzlv	int	被动买特大单成交量增量
bdmbddcjzlv	int	被动买大单成交量增量
bdmbzdcjzlv	int	被动买中单成交量增量
bdmbxdcjzlv	int	被动买小单成交量增量
bdmbljcjzlv	int	被动买累计成交量增量
bdmstdcjzlv	int	被动卖特大单成交量增量
bdmsddcjzlv	int	被动卖大单成交量增量
bdmszdcjzlv	int	被动卖中单成交量增量
bdmsxdcjzlv	int	被动卖小单成交量增量


最新分时交易
API地址：https://api.zhituapi.cn/hs/latest/股票代码.市场（如000001.SZ）/分时级别(如d)/除权方式?token=token证书&limit=最新条数(例如2)

描述：根据《股票列表》得到的股票代码和分时级别获取最新交易数据，交易时间升序。目前分时级别支持、5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为5、15、30、60、d、w、m、y，除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br，分钟级无除权数据，对应的参数为n。同时可以指定获取数据条数，例如指定lt=20，则获取最新的20条数据。

更新频率：实时

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易时间
o	float	开盘价
h	float	最高价
l	float	最低价
c	float	收盘价
v	float	成交量
a	float	成交额
pc	float	前收盘价
sf	int	停牌 1停牌，0 不停牌


历史分时交易
API地址：https://api.zhituapi.cn/hs/history/股票代码.市场（如000001.SZ）/分时级别(如d)/除权方式?token=token证书&st=开始时间(如20240601)&et=结束时间(如20250430)

描述：根据《股票列表》得到的股票代码和分时级别获取历史交易数据，交易时间升序。目前分时级别支持5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为5、15、30、60、d、w、m、y，除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br，分钟级无除权数据，对应的参数为n。开始时间以及结束时间的格式均为 YYYYMMDD 或 YYYYMMDDhhmmss，例如：'20240101' 或'20241231235959'。不设置开始时间和结束时间则为全部历史数据。

更新频率：分钟级别数据盘中更新，分时越小越优先更新，如5分钟级别会每5分钟更新，15分钟级别会每15分钟更新，以此类推，日线及以上级别每日15:30开始更新，预计17:10完成

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易时间
o	float	开盘价
h	float	最高价
l	float	最低价
c	float	收盘价
v	float	成交量
a	float	成交额
pc	float	前收盘价
sf	int	停牌 1停牌，0 不停牌


历史涨跌停价格
API地址：http://api.zhituapi.cn/hs/stopprice/history/股票代码（如000001.SZ）?token=token证书&st=开始时间&et=结束时间

描述：根据《股票列表》得到的股票代码获取历史涨跌停价格，开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'。不设置开始时间和结束时间则为全部历史数据。

更新频率：每日0点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易日期
h	float	涨停价格
l	float	跌停价格

股票基础信息
API地址：http://api.zhituapi.cn/hs/instrument/股票代码（如000001.SZ）?token=token证书

描述：依据《股票列表》中的股票代码获取股票的基础信息

更新频率：每日1点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
ei	string	市场代码
ii	string	股票代码
name	string	股票名称
od	string	上市日期(股票IPO日期)
pc	float	前收盘价格
up	float	当日涨停价
dp	float	当日跌停价
fv	float	流通股本
tv	float	总股本
pk	float	最小价格变动单位
is	int	股票停牌状态(<=0:正常交易（-1:复牌）;>=1停牌天数;)


历史分时MACD
API地址：https://api.zhituapi.cn/hs/history/macd/股票代码(如000001.SZ)/分时级别(如d)/除权类型(如n)?token=token证书&st=开始时间&et=结束时间&lt=最新条数

描述：根据《股票列表》得到的股票代码和分时级别获取历史MACD数据，交易时间升序。目前分时级别支持5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为5、15、30、60、d、w、m、y，日线以上除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br，分钟级仅限请求不复权数据，对应的参数为n。开始时间以及结束时间的格式均为 YYYYMMDD 或 YYYYMMDDhhmmss，例如：'20240101' 或'20241231235959'。不设置开始时间和结束时间则为全部历史数据。同时可以指定获取数据条数，例如指定lt=10，则获取最新的10条数据。

更新频率：分钟级别数据盘中更新，分时越小越优先更新，如5分钟级别会每5分钟更新，15分钟级别会每15分钟更新，以此类推，日线及以上级别每日15:35更新

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易时间，短分时级别格式为yyyy-MM-ddHH:mm:ss，日线级别为yyyy-MM-dd
diff	number	DIFF值
dea	number	DEA值
macd	number	MACD值
ema12	number	EMA（12）值
ema26	number	EMA（26）值


历史分时MA
API地址：https://api.zhituapi.cn/hs/history/ma/股票代码(如000001.SZ)/分时级别(如d)/除权类型(如n)?token=token证书&st=开始时间&et=结束时间&lt=最新条数

描述：根据《股票列表》得到的股票代码和分时级别获取历史MA数据，交易时间升序。目前分时级别支持5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为5、15、30、60、d、w、m、y，日线以上除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br，分钟级仅限请求不复权数据，对应的参数为n。开始时间以及结束时间的格式均为 YYYYMMDD 或 YYYYMMDDhhmmss，例如：'20240101' 或'20241231235959'。不设置开始时间和结束时间则为全部历史数据。同时可以指定获取数据条数，例如指定lt=10，则获取最新的10条数据。

更新频率：分钟级别数据盘中更新，分时越小越优先更新，如5分钟级别会每5分钟更新，15分钟级别会每15分钟更新，以此类推，日线及以上级别每日15:35更新

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易时间，短分时级别格式为yyyy-MM-ddHH:mm:ss，日线级别为yyyy-MM-dd
ma3	number	MA3，没有则为null
ma5	number	MA5，没有则为null
ma10	number	MA10，没有则为null
ma15	number	MA15，没有则为null
ma20	number	MA20，没有则为null
ma30	number	MA30，没有则为null
ma60	number	MA60，没有则为null
ma120	number	MA120，没有则为null
ma200	number	MA200，没有则为null
ma250	number	MA250，没有则为null


历史分时BOLL
API地址：https://api.zhituapi.cn/hs/history/boll/股票代码(如000001.SZ)/分时级别(如d)/除权类型(如n)?token=token证书&st=开始时间&et=结束时间&lt=最新条数

描述：根据《股票列表》得到的股票代码和分时级别获取历史BOLL数据，交易时间升序。目前分时级别支持5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为5、15、30、60、d、w、m、y，日线以上除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br，分钟级仅限请求不复权数据，对应的参数为n。开始时间以及结束时间的格式均为 YYYYMMDD 或 YYYYMMDDhhmmss，例如：'20240101' 或'20241231235959'。不设置开始时间和结束时间则为全部历史数据。同时可以指定获取数据条数，例如指定lt=10，则获取最新的10条数据。

更新频率：分钟级别数据盘中更新，分时越小越优先更新，如5分钟级别会每5分钟更新，15分钟级别会每15分钟更新，以此类推，日线及以上级别每日15:35更新

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易时间，短分时级别格式为yyyy-MM-ddHH:mm:ss，日线级别为yyyy-MM-dd
u	number	上轨
d	number	下轨
m	number	中轨


历史分时KDJ
API地址：https://api.zhituapi.cn/hs/history/kdj/股票代码(如000001.SZ)/分时级别(如d)/除权类型(如n)?token=token证书&st=开始时间&et=结束时间&lt=最新条数

描述：根据《股票列表》得到的股票代码和分时级别获取历史KDJ数据，交易时间升序。目前分时级别支持5分钟、15分钟、30分钟、60分钟、日线、周线、月线、年线，对应的请求参数分别为5、15、30、60、d、w、m、y，日线以上除权方式有不复权、前复权、后复权、等比前复权、等比后复权，对应的参数分别为n、f、b、fr、br，分钟级仅限请求不复权数据，对应的参数为n。开始时间以及结束时间的格式均为 YYYYMMDD 或 YYYYMMDDhhmmss，例如：'20240101' 或'20241231235959'。不设置开始时间和结束时间则为全部历史数据。同时可以指定获取数据条数，例如指定lt=10，则获取最新的10条数据。

更新频率：分钟级别数据盘中更新，分时越小越优先更新，如5分钟级别会每5分钟更新，15分钟级别会每15分钟更新，以此类推，日线及以上级别每日15:35更新

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
t	string	交易时间，短分时级别格式为yyyy-MM-ddHH:mm:ss，日线级别为yyyy-MM-dd
k	number	K值
d	number	D值
j	number	J值


资产负债表
API地址：https://api.zhituapi.cn/hs/fin/balance/股票代码（如000001.SZ）?token=token证书&st=开始时间&et=结束时间

描述：根据《股票列表》得到的股票代码获取资产负债表，开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'。不设置开始时间和结束时间则为全部数据。

更新频率：每日0点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
jzrq	string	截止日期
plrq	string	披露日期
nbysk	float	内部应收款
gdzcql	float	固定资产清理
yffbzk	float	应付分保账款
jsbfj	float	结算备付金
ysbf	float	应收保费
ysfbzk	float	应收分保账款
ysfbhtzbj	float	应收分保合同准备金
ysgl	float	应收股利
ysckts	float	应收出口退税
ysbtk	float	应收补贴款
ysbzj	float	应收保证金
dfy	float	待摊费用
dclldzcsy	float	待处理流动资产损益
ynndqdfldzc	float	一年内到期的非流动资产
cqysk	float	长期应收款
qtcqtz	float	其他长期投资
gdzcyz	float	固定资产原值
gdzcjz	float	固定资产净值
gdzcjzzbj	float	固定资产减值准备
scxswzc	float	生产性生物资产
gyxswzc	float	公益性生物资产
yqzc	float	油气资产
kfzc	float	开发支出
gqfzltq	float	股权分置流通权
qtfldzc	float	其他非流动资产
yfsxfyj	float	应付手续费及佣金
qtjyk	float	其他应交款
yfbzj	float	应付保证金
nbyfk	float	内部应付款
ytfy	float	预提费用
bxhtzbj	float	保险合同准备金
dlmmzqk	float	代理买卖证券款
dlcxzqk	float	代理承销证券款
gjpjjs	float	国际票证结算
gnpjjs	float	国内票证结算
dysr	float	递延收益
yfdqzq	float	应付短期债券
cqdysr	float	长期递延收益
wqddtzss	float	未确定的投资损失
nfpxjgl	float	拟分配现金股利
yjfz	float	预计负债
xsckjtycf	float	吸收存款及同业存放
yjldfz	float	预计流动负债
j_kcg	float	减:库存股
hbzj	float	货币资金
cczj	float	拆出资金
jyxjrzc	float	交易性金融资产
ysjrzc	float	衍生金融资产
yspj	float	应收票据
yszk	float	应收账款
yfkx	float	预付款项
yslx	float	应收利息
qtysk	float	其他应收款
mrfsjrzck	float	买入返售金融资产款
gyjzjzbdqjsrdq	float	以公允价值计量且其变动计入当期损益的金融资产
ch	float	存货
qtldzc	float	其他流动资产
ldzchj	float	流动资产合计
ffdkjjd	float	发放贷款及垫款
kkgsjrzc	float	可供出售金融资产
cyzdqtz	float	持有至到期投资
cqgqtz	float	长期股权投资
tzxfd	float	投资性房地产
ljzj	float	累计折旧
gdzc	float	固定资产
zjgc	float	在建工程
gcwz	float	工程物资
cqfz	float	长期负债
wxzc	float	无形资产
sy	float	商誉
cqdtfy	float	长期待摊费用
dysdszc	float	递延所得税资产
fldzchj	float	非流动资产合计
zczj	float	资产总计
dqjk	float	短期借款
xzyhyhk	float	向中央银行借款
crzj	float	拆入资金
jyxjrfz	float	交易性金融负债
ysjrfz	float	衍生金融负债
yfpj	float	应付票据
yfzk	float	应付账款
ysk	float	预收账款
mchgjrzck	float	卖出回购金融资产款
yfgzxc	float	应付职工薪酬
yjsf	float	应交税费
yflx	float	应付利息
yfgl	float	应付股利
qtfzk	float	其他应付款
ynndqdfldfz	float	一年内到期的非流动负债
qtldfz	float	其他流动负债
ldfzhj	float	流动负债合计
cqjk	float	长期借款
yfzq	float	应付债券
cqyfk	float	长期应付款
zxyfk	float	专项应付款
dysdsfz	float	递延所得税负债
qtfldfz	float	其他非流动负债
fldfzhj	float	非流动负债合计
fzhj	float	负债合计
sszb	float	实收资本(或股本)
zbgj	float	资本公积
zxzb	float	专项储备
ylgj	float	盈余公积
ybfxzb	float	一般风险准备
wfplr	float	未分配利润
wbbzbzhc	float	外币报表折算差额
gsmgdqsyhj	float	归属于母公司股东权益合计
ssgdqy	float	少数股东权益
syzqyhj	float	所有者权益合计
fzhgdqyzj	float	负债和股东权益总计


利润表
API地址：https://api.zhituapi.cn/hs/fin/income/股票代码（如000001.SZ）?token=token证书&st=开始时间&et=结束时间

描述：根据《股票列表》得到的股票代码获取利润表，开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'。不设置开始时间和结束时间则为全部数据。

更新频率：每日0点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
jzrq	string	截止日期
plrq	string	披露日期
yysr	float	营业收入
yzbf	float	已赚保费
fdczssr	float	房地产销售收入
yyzcb	float	营业总成本
fdczscb	float	房地产销售成本
yffy	float	研发费用
tbj	float	退保金
pczjje	float	赔付支出净额
tqbxhtzbjje	float	提取保险合同准备金净额
bdhlzc	float	保单红利支出
fbfy	float	分保费用
gyjzbdsy	float	公允价值变动收益
qhsy	float	期货损益
tgsy	float	托管收益
btsr	float	补贴收入
qtywlr	float	其他业务利润
bhbfzhbqsljlr	float	被合并方在合并前实现净利润
lxsr	float	利息收入
sxfjyjsr	float	手续费及佣金收入
sxfjyjzc	float	手续费及佣金支出
qtywcb	float	其他业务成本
hdsy	float	汇兑收益
fldzcczsy	float	非流动资产处置收益
sdsfy	float	所得税费用
wqrtzss	float	未确认投资损失
gsmgsyzzdjlr	float	归属于母公司所有者的净利润
lxzc	float	利息支出
qtywsr	float	其他业务收入
yyzsr	float	营业总收入
yycb	float	营业成本
yysjjfj	float	营业税金及附加
xsfy	float	销售费用
glfy	float	管理费用
cwfy	float	财务费用
zcjzss	float	资产减值损失
tzsy	float	投资收益
lyqyhhhqydtzsy	float	联营企业和合营企业的投资收益
yylr	float	营业利润
ywsr	float	营业外收入
ywzc	float	营业外支出
lrze	float	利润总额
jlr	float	净利润
jlrhfcjcx	float	净利润(扣除非经常性损益后)
ssgdsy	float	少数股东损益
jbmgsy	float	基本每股收益
xsmgsy	float	稀释每股收益
zhsyz	float	综合收益总额
gsssgdzhsyz	float	归属于少数股东的综合收益总额
qtsy	float	其他收益

现金流量表
API地址：https://api.zhituapi.cn/hs/fin/cashflow/股票代码（如000001.SZ）?token=token证书&st=开始时间&et=结束时间

描述：根据《股票列表》得到的股票代码获取现金流量表，开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'。不设置开始时间和结束时间则为全部数据。

更新频率：每日0点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
jzrq	string	截止日期
plrq	string	披露日期
sdydbxbfqdxj	float	收到原保险合同保费取得的现金
sdzbxywxjjje	float	收到再保险业务现金净额
bhcjjtkkjzje	float	保户储金及投资款净增加额
czjyxjrzcjzje	float	处置交易性金融资产净增加额
sqlxsxfjyjdxj	float	收取利息、手续费及佣金的现金
hgywzjjzje	float	回购业务资金净增加额
zfybxhtpfkxdj	float	支付原保险合同赔付款项的现金
zfbdhldxj	float	支付保单红利的现金
czfzgsjqtsddxj	float	处置子公司及其他收到的现金
jszyhdqckssddxj	float	减少质押和定期存款所收到的现金
tzszfdxj	float	投资所支付的现金
zydkjzje	float	质押贷款净增加额
qdfzgsjqtywdwzfdxjje	float	取得子公司及其他营业单位支付的现金净额
zjzyhdqckszfdxj	float	增加质押和定期存款所支付的现金
qzfzgsxrxj	float	其中子公司吸收现金
qz:fzgszfgsssgdglr	float	其中:子公司支付给少数股东的股利、利润
ssgdsy	float	少数股东损益
wqrdtzss	float	未确认的投资损失
dysyzj(j:js)	float	递延收益增加(减:减少)
yjfz	float	预计负债
jxyyfxmdzj	float	经营性应付项目的增加
ywgwswjskdjs(j:zj)	float	已完工尚未结算款的减少(减:增加)
yjswgwgdjz(j:js)	float	已结算尚未完工款的增加(减:减少)
xssptglwsddxj	float	销售商品、提供劳务收到的现金
khckhtyckxkjzje	float	客户存款和同业存放款项净增加额
xzyhyhkjzje	float	向中央银行借款净增加额(万元)
xtjrgjqjcrzjjzje	float	向其他金融机构拆入资金净增加额
sddsfyfh	float	收到的税费与返还
tzzfdxj	float	投资支付的现金
sdqtyjyghdxj	float	收到的其他与经营活动有关的现金
jyhdxjlrxj	float	经营活动现金流入小计
gmspjslwzfdxj	float	购买商品、接受劳务支付的现金
khdkjdknzje	float	客户贷款及垫款净增加额
cfzyxhytckxkjzje	float	存放中央银行和同业款项净增加额
zflxsxfjyjdxj	float	支付利息、手续费及佣金的现金
zfgzyjwzgzfdxj	float	支付给职工以及为职工支付的现金
zfdgxsf	float	支付的各项税费
zfqtyjyghdxj	float	支付其他与经营活动有关的现金
jyhdxjlcxj	float	经营活动现金流出小计
jyhdcsdxjlje	float	经营活动产生的现金流量净额
shtzssddxj	float	收回投资所收到的现金
qdtzsysddxj	float	取得投资收益所收到的现金
czgdzcwxzhqtqctzssddxj	float	处置固定资产、无形资产和其他长期投资收到的现金
sdqtytzghdxj	float	收到的其他与投资活动有关的现金
tzhdxjlrxj	float	投资活动现金流入小计
gjgdzcwxzhqtqctzzfdxj	float	购建固定资产、无形资产和其他长期投资支付的现金
tzhdxjlcxj	float	投资活动现金流出小计
tzhdcsdxjlxj	float	投资活动产生的现金流量净额
xstzsdj	float	吸收投资收到的现金
qdjkjddxj	float	取得借款收到的现金
fxzjsddxj	float	发行债券收到的现金
sdqtczghdxj	float	收到其他与筹资活动有关的现金
czhdxjlrxj	float	筹资活动现金流入小计
chzwzfxj	float	偿还债务支付现金
fpglrlhcllxzfdxj	float	分配股利、利润或偿付利息支付的现金
zfqtczdxj	float	支付其他与筹资的现金
czhdxjlcxj	float	筹资活动现金流出小计
czhdcsdxjlxj	float	筹资活动产生的现金流量净额
hlbddxjdxy	float	汇率变动对现金的影响
xjxjdhwjzje	float	现金及现金等价物净增加额
qcxjjxjdhwye	float	期初现金及现金等价物余额
qmxjjxjdhwye	float	期末现金及现金等价物余额
jlr	float	净利润
zcjzzb	float	资产减值准备
gdzczjyqzcshscxwzczj	float	固定资产折旧、油气资产折耗、生产性物资折旧
wxzctx	float	无形资产摊销
cqdtfytx	float	长期待摊费用摊销
dtfydjs	float	待摊费用的减少
ytfydzj	float	预提费用的增加
czgdzcwxzhqtqctzss	float	处置固定资产、无形资产和其他长期资产的损失
gdzcgbss	float	固定资产报废损失
gyjzbds	float	公允价值变动损失
cwfy	float	财务费用
tzss	float	投资损失
dysdszcjs	float	递延所得税资产减少
dysdsfzzj	float	递延所得税负债增加
chdjs	float	存货的减少
jxyysxmdjs	float	经营性应收项目的减少
qt	float	其他
jyhdcsdxjlxj	float	经营活动产生现金流量净额
zwzwzb	float	债务转为资本
ynndqdkzhgzq	float	一年内到期的可转换公司债券
rzrgdzc	float	融资租入固定资产
xjdqmye	float	现金的期末余额
xjdqcye	float	现金的期初余额
xjdhwdqmye	float	现金等价物的期末余额
xjdhwdqcye	float	现金等价物的期初余额
xjxjdhwdjzje	float	现金及现金等价物的净增加额


财务主要指标
API地址：https://api.zhituapi.cn/hs/fin/ratios/股票代码（如000001.SZ）?token=token证书&st=开始时间&et=结束时间

描述：根据《股票列表》得到的股票代码获取财务主要指标，开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'。不设置开始时间和结束时间则为全部数据。

更新频率：每日0点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次
字段名称	数据类型	字段说明
mgzbgjj	float	每股资本公积金
kfmgsy	float	扣非每股收益
jzcsyl	float	净资产收益率
xsmlv	float	销售毛利率
zyyrsrzz	float	主营收入同比增长
jlrzz	float	净利润同比增长
gsmgsyzzdjlrzz	float	归属于母公司所有者的净利润同比增长
kfjlrzz	float	扣非净利润同比增长
yyzsrgdhbzz	float	营业总收入滚动环比增长
sljlrjqhbzz	float	归属净利润滚动环比增长
kfjlrgdhbzz	float	扣非净利润滚动环比增长
jqjzcsyl	float	加权净资产收益率
tbjzcsyl	float	摊薄净资产收益率
tbzzcsyl	float	摊薄总资产收益率
mlv	float	毛利率
jlv	float	净利率
sjslv	float	实际税率
yskyysr	float	预收款营业收入
xsxjlyysr	float	销售现金流营业收入
zcfzl	float	资产负债比率
chzzl	float	存货周转率


公司股本表
API地址：https://api.zhituapi.cn/hs/fin/capital/股票代码（如000001.SZ）?token=token证书&st=开始时间&et=结束时间

描述：根据《股票列表》得到的股票代码获取公司股本表，开始时间以及结束时间的格式均为 YYYYMMDD，例如：'20240101'。不设置开始时间和结束时间则为全部数据。

更新频率：每日0点

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
zgb	float	总股本
ysltag	float	已上市流通A股
xsltgf	float	限售流通股份
bdrq	string	变动日期
ggr	string	公告日



公司简介
API地址：https://api.zhituapi.cn/hs/gs/gsjj/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的简介。包括公司基本信息，概念以及发行信息等。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
name	string	公司名称
ename	string	公司英文名称
market	string	上市市场
idea	string	概念及板块，多个概念由英文逗号分隔
ldate	string	上市日期，格式yyyy-MM-dd
sprice	string	发行价格（元）
principal	string	主承销商
rdate	string	成立日期
rprice	string	注册资本
instype	string	机构类型
organ	string	组织形式
secre	string	董事会秘书
phone	string	公司电话
sphone	string	董秘电话
fax	string	公司传真
sfax	string	董秘传真
email	string	公司电子邮箱
semail	string	董秘电子邮箱
site	string	公司网站
post	string	邮政编码
infosite	string	信息披露网址
oname	string	证券简称更名历史
addr	string	注册地址
oaddr	string	办公地址
desc	string	公司简介
bscope	string	经营范围
printype	string	承销方式
referrer	string	上市推荐人
putype	string	发行方式
pe	string	发行市盈率（按发行后总股本）
firgu	string	首发前总股本（万股）
lastgu	string	首发后总股本（万股）
realgu	string	实际发行量（万股）
planm	string	预计募集资金（万元）
realm	string	实际募集资金合计（万元）
pubfee	string	发行费用总额（万元）
collect	string	募集资金净额（万元）
signfee	string	承销费用（万元）
pdate	string	招股公告日


所属指数
API地址：https://api.zhituapi.cn/hs/gs/sszs/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的所属指数。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次
字段名称	数据类型	字段说明
mc	string	指数名称
dm	string	指数代码
ind	string	进入日期yyyy-MM-dd
outd	string	退出日期yyyy-MM-dd


历届高管成员
API地址：https://api.zhituapi.cn/hs/gs/ljgg/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的历届高管成员名单。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次
字段名称	数据类型	字段说明
name	string	姓名
title	string	职务
sdate	string	起始日期yyyy-MM-dd
edate	string	终止日期yyyy-MM-dd

历届董事会成员
API地址：https://api.zhituapi.cn/hs/gs/ljds/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的历届董事会成员名单。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
name	string	姓名
title	string	职务
sdate	string	起始日期yyyy-MM-dd
edate	string	终止日期yyyy-MM-dd


历届监事会成员
API地址：https://api.zhituapi.cn/hs/gs/ljjs/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的历届监事会成员名单。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
name	string	姓名
title	string	职务
sdate	string	起始日期yyyy-MM-dd
edate	string	终止日期yyyy-MM-dd


近年分红
API地址：https://api.zhituapi.cn/hs/gs/jnff/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的近年来的分红实施结果。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
sdate	string	公告日期yyyy-MM-dd
give	string	每10股送股(单位：股)
change	string	每10股转增(单位：股)
send	string	每10股派息(税前，单位：元)
line	string	进度
cdate	string	除权除息日yyyy-MM-dd
edate	string	股权登记日yyyy-MM-dd
hdate	string	红股上市日yyyy-MM-dd

近年增发
API地址：https://api.zhituapi.cn/hs/gs/jnzf/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的近年来的增发情况。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次


字段名称	数据类型	字段说明
sdate	string	公告日期yyyy-MM-dd
type	string	发行方式
price	string	发行价格
tprice	string	实际公司募集资金总额
fprice	string	发行费用总额
amount	string	实际发行数量


解禁限售
API地址：https://api.zhituapi.cn/hs/gs/jjxs/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的解禁限售情况。按解禁日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
rdate	string	解禁日期yyyy-MM-dd
ramount	number	解禁数量(万股)
rprice	number	解禁股流通市值(亿元)
batch	number	上市批次
pdate	string	公告日期yyyy-MM-dd


近一年各季度利润
API地址：https://api.zhituapi.cn/hs/gs/jdlr/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近一年各个季度的利润。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
date	string	截止日期yyyy-MM-dd
income	string	营业收入（万元）
expend	string	营业支出（万元）
profit	string	营业利润（万元）
totalp	string	利润总额（万元）
reprofit	string	净利润（万元）
basege	string	基本每股收益(元/股)
ettege	string	稀释每股收益(元/股)
otherp	string	其他综合收益（万元）
totalcp	string	综合收益总额（万元）

近一年各季度现金流
API地址：https://api.zhituapi.cn/hs/gs/jdxj/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近一年各个季度的现金流。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
date	string	截止日期yyyy-MM-dd
jyin	string	经营活动现金流入小计（万元）
jyout	string	经营活动现金流出小计（万元）
jyfinal	string	经营活动产生的现金流量净额（万元）
tzin	string	投资活动现金流入小计（万元）
tzout	string	投资活动现金流出小计（万元）
tzfinal	string	投资活动产生的现金流量净额（万元）
czin	string	筹资活动现金流入小计（万元）
czout	string	筹资活动现金流出小计（万元）
czfinal	string	筹资活动产生的现金流量净额（万元）
hl	string	汇率变动对现金及现金等价物的影响（万元）
cashinc	string	现金及现金等价物净增加额（万元）
cashs	string	期初现金及现金等价物余额（万元）
cashe	string	期末现金及现金等价物余额（万元）


近年业绩预告
API地址：https://api.zhituapi.cn/hs/gs/yjyg/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近年来的业绩预告。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
pdate	string	公告日期yyyy-MM-dd
rdate	string	报告期yyyy-MM-dd
type	string	类型
abs	string	业绩预告摘要
old	string	上年同期每股收益(元)

财务指标
API地址：https://api.zhituapi.cn/hs/gs/cwzb/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近四个季度的主要财务指标。按报告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
date	string	报告日期yyyy-MM-dd
tbmg	string	摊薄每股收益(元)d
jqmg	string	加权每股收益(元)型
mgsy	string	每股收益_调整后(元)
kfmg	string	扣除非经常性损益后的每股收益(元)
mgjz	string	每股净资产_调整前(元)
mgjzad	string	每股净资产_调整后(元)
mgjy	string	每股经营性现金流(元)
mggjj	string	每股资本公积金(元)
mgwly	string	每股未分配利润(元)
zclr	string	总资产利润率(%)
zylr	string	主营业务利润率(%)
zzlr	string	总资产净利润率(%)
cblr	string	成本费用利润率(%)
yylr	string	营业利润率(%)
zycb	string	主营业务成本率(%)
xsjl	string	销售净利率(%)
gbbc	string	股本报酬率(%)
jzbc	string	净资产报酬率(%)
zcbc	string	资产报酬率(%)
xsml	string	销售毛利率(%)
xxbz	string	三项费用比重
fzy	string	非主营比重
zybz	string	主营利润比重
gxff	string	股息发放率(%)
tzsy	string	投资收益率(%)
zyyw	string	主营业务利润(元)
jzsy	string	净资产收益率(%)
jqjz	string	加权净资产收益率(%)
kflr	string	扣除非经常性损益后的净利润(元)
zysr	string	主营业务收入增长率(%)
jlzz	string	净利润增长率(%)
jzzz	string	净资产增长率(%)
zzzz	string	总资产增长率(%)
yszz	string	应收账款周转率(次)
yszzt	string	应收账款周转天数(天)
chzz	string	存货周转天数(天)
chzzl	string	存货周转率(次)
gzzz	string	固定资产周转率(次)
zzzzl	string	总资产周转率(次)
zzzzt	string	总资产周转天数(天)
ldzz	string	流动资产周转率(次)
ldzzt	string	流动资产周转天数(天)
gdzz	string	股东权益周转率(次)
ldbl	string	流动比率
sdbl	string	速动比率
xjbl	string	现金比率(%)
lxzf	string	利息支付倍数
zjbl	string	长期债务与营运资金比率(%)
gdqy	string	股东权益比率(%)
cqfz	string	长期负债比率(%)
gdgd	string	股东权益与固定资产比率(%)
fzqy	string	负债与所有者权益比率(%)
zczjbl	string	长期资产与长期资金比率(%)
zblv	string	资本化比率(%)
gdzcjz	string	固定资产净值率(%)
zbgdh	string	资本固定化比率(%)
cqbl	string	产权比率(%)
qxjzb	string	清算价值比率(%)
gdzcbz	string	固定资产比重(%)
zcfzl	string	资产负债率(%)
zzc	string	总资产(元)
jyxj	string	经营现金净流量对销售收入比率(%)
zcjyxj	string	资产的经营现金流量回报率(%)
jylrb	string	经营现金净流量与净利润的比率(%)
jyfzl	string	经营现金净流量对负债比率(%)
xjlbl	string	现金流量比率(%)
dqgptz	string	短期股票投资(元)
dqzctz	string	短期债券投资(元)
dqjytz	string	短期其它经营性投资(元)
qcgptz	string	长期股票投资(元)
cqzqtz	string	长期债券投资(元)
cqjyxtz	string	长期其它经营性投资(元)
yszk1	string	1年以内应收帐款(元)
yszk12	string	1-2年以内应收帐款(元)
yszk23	string	2-3年以内应收帐款(元)
yszk3	string	3年以内应收帐款(元)
yfhk1	string	1年以内预付货款(元)
yfhk12	string	1-2年以内预付货款(元)
yfhk23	string	2-3年以内预付货款(元)
yfhk3	string	3年以内预付货款(元)
ysk1	string	1年以内其它应收款(元)
ysk12	string	1-2年以内其它应收款(元)
ysk23	string	2-3年以内其它应收款(元)
ysk3	string	3年以内其它应收款(元)

十大股东
API地址：https://api.zhituapi.cn/hs/gs/sdgd/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的十大股东数据。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

jzrq	string	截止日期yyyy-MM-dd
ggrq	string	公告日期yyyy-MM-dd
gdsm	string	股东说明
gdzs	number	股东总数
pjcg	number	平均持股(单位：股，按总股本计算)
sdgd	array<ZygdSdgd>	十大股东，其中ZygdSdgd对象见下方说明

十大流通股东
API地址：https://api.zhituapi.cn/hs/gs/ltgd/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的十大流通股东数据。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
jzrq	string	截止日期yyyy-MM-dd
ggrq	string	公告日期yyyy-MM-dd
sdgd	array<ZygdSdgd>	十大流通股东，其中ZygdSdgd对象见下方说明


涨跌股池
上市公司详情
实时交易
行情数据
基础信息
技术指标
财务报表
公司简介
API地址：https://api.zhituapi.cn/hs/gs/gsjj/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的简介。包括公司基本信息，概念以及发行信息等。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
name	string	公司名称
ename	string	公司英文名称
market	string	上市市场
idea	string	概念及板块，多个概念由英文逗号分隔
ldate	string	上市日期，格式yyyy-MM-dd
sprice	string	发行价格（元）
principal	string	主承销商
rdate	string	成立日期
rprice	string	注册资本
instype	string	机构类型
organ	string	组织形式
secre	string	董事会秘书
phone	string	公司电话
sphone	string	董秘电话
fax	string	公司传真
sfax	string	董秘传真
email	string	公司电子邮箱
semail	string	董秘电子邮箱
site	string	公司网站
post	string	邮政编码
infosite	string	信息披露网址
oname	string	证券简称更名历史
addr	string	注册地址
oaddr	string	办公地址
desc	string	公司简介
bscope	string	经营范围
printype	string	承销方式
referrer	string	上市推荐人
putype	string	发行方式
pe	string	发行市盈率（按发行后总股本）
firgu	string	首发前总股本（万股）
lastgu	string	首发后总股本（万股）
realgu	string	实际发行量（万股）
planm	string	预计募集资金（万元）
realm	string	实际募集资金合计（万元）
pubfee	string	发行费用总额（万元）
collect	string	募集资金净额（万元）
signfee	string	承销费用（万元）
pdate	string	招股公告日
所属指数
API地址：https://api.zhituapi.cn/hs/gs/sszs/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的所属指数。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
mc	string	指数名称
dm	string	指数代码
ind	string	进入日期yyyy-MM-dd
outd	string	退出日期yyyy-MM-dd
历届高管成员
API地址：https://api.zhituapi.cn/hs/gs/ljgg/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的历届高管成员名单。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
name	string	姓名
title	string	职务
sdate	string	起始日期yyyy-MM-dd
edate	string	终止日期yyyy-MM-dd
历届董事会成员
API地址：https://api.zhituapi.cn/hs/gs/ljds/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的历届董事会成员名单。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
name	string	姓名
title	string	职务
sdate	string	起始日期yyyy-MM-dd
edate	string	终止日期yyyy-MM-dd
历届监事会成员
API地址：https://api.zhituapi.cn/hs/gs/ljjs/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的历届监事会成员名单。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
name	string	姓名
title	string	职务
sdate	string	起始日期yyyy-MM-dd
edate	string	终止日期yyyy-MM-dd
近年分红
API地址：https://api.zhituapi.cn/hs/gs/jnff/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的近年来的分红实施结果。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
sdate	string	公告日期yyyy-MM-dd
give	string	每10股送股(单位：股)
change	string	每10股转增(单位：股)
send	string	每10股派息(税前，单位：元)
line	string	进度
cdate	string	除权除息日yyyy-MM-dd
edate	string	股权登记日yyyy-MM-dd
hdate	string	红股上市日yyyy-MM-dd
近年增发
API地址：https://api.zhituapi.cn/hs/gs/jnzf/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的近年来的增发情况。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
sdate	string	公告日期yyyy-MM-dd
type	string	发行方式
price	string	发行价格
tprice	string	实际公司募集资金总额
fprice	string	发行费用总额
amount	string	实际发行数量
解禁限售
API地址：https://api.zhituapi.cn/hs/gs/jjxs/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的解禁限售情况。按解禁日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
rdate	string	解禁日期yyyy-MM-dd
ramount	number	解禁数量(万股)
rprice	number	解禁股流通市值(亿元)
batch	number	上市批次
pdate	string	公告日期yyyy-MM-dd
近一年各季度利润
API地址：https://api.zhituapi.cn/hs/gs/jdlr/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近一年各个季度的利润。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
date	string	截止日期yyyy-MM-dd
income	string	营业收入（万元）
expend	string	营业支出（万元）
profit	string	营业利润（万元）
totalp	string	利润总额（万元）
reprofit	string	净利润（万元）
basege	string	基本每股收益(元/股)
ettege	string	稀释每股收益(元/股)
otherp	string	其他综合收益（万元）
totalcp	string	综合收益总额（万元）
近一年各季度现金流
API地址：https://api.zhituapi.cn/hs/gs/jdxj/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近一年各个季度的现金流。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
date	string	截止日期yyyy-MM-dd
jyin	string	经营活动现金流入小计（万元）
jyout	string	经营活动现金流出小计（万元）
jyfinal	string	经营活动产生的现金流量净额（万元）
tzin	string	投资活动现金流入小计（万元）
tzout	string	投资活动现金流出小计（万元）
tzfinal	string	投资活动产生的现金流量净额（万元）
czin	string	筹资活动现金流入小计（万元）
czout	string	筹资活动现金流出小计（万元）
czfinal	string	筹资活动产生的现金流量净额（万元）
hl	string	汇率变动对现金及现金等价物的影响（万元）
cashinc	string	现金及现金等价物净增加额（万元）
cashs	string	期初现金及现金等价物余额（万元）
cashe	string	期末现金及现金等价物余额（万元）
近年业绩预告
API地址：https://api.zhituapi.cn/hs/gs/yjyg/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近年来的业绩预告。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
pdate	string	公告日期yyyy-MM-dd
rdate	string	报告期yyyy-MM-dd
type	string	类型
abs	string	业绩预告摘要
old	string	上年同期每股收益(元)
财务指标
API地址：https://api.zhituapi.cn/hs/gs/cwzb/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司近四个季度的主要财务指标。按报告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
date	string	报告日期yyyy-MM-dd
tbmg	string	摊薄每股收益(元)d
jqmg	string	加权每股收益(元)型
mgsy	string	每股收益_调整后(元)
kfmg	string	扣除非经常性损益后的每股收益(元)
mgjz	string	每股净资产_调整前(元)
mgjzad	string	每股净资产_调整后(元)
mgjy	string	每股经营性现金流(元)
mggjj	string	每股资本公积金(元)
mgwly	string	每股未分配利润(元)
zclr	string	总资产利润率(%)
zylr	string	主营业务利润率(%)
zzlr	string	总资产净利润率(%)
cblr	string	成本费用利润率(%)
yylr	string	营业利润率(%)
zycb	string	主营业务成本率(%)
xsjl	string	销售净利率(%)
gbbc	string	股本报酬率(%)
jzbc	string	净资产报酬率(%)
zcbc	string	资产报酬率(%)
xsml	string	销售毛利率(%)
xxbz	string	三项费用比重
fzy	string	非主营比重
zybz	string	主营利润比重
gxff	string	股息发放率(%)
tzsy	string	投资收益率(%)
zyyw	string	主营业务利润(元)
jzsy	string	净资产收益率(%)
jqjz	string	加权净资产收益率(%)
kflr	string	扣除非经常性损益后的净利润(元)
zysr	string	主营业务收入增长率(%)
jlzz	string	净利润增长率(%)
jzzz	string	净资产增长率(%)
zzzz	string	总资产增长率(%)
yszz	string	应收账款周转率(次)
yszzt	string	应收账款周转天数(天)
chzz	string	存货周转天数(天)
chzzl	string	存货周转率(次)
gzzz	string	固定资产周转率(次)
zzzzl	string	总资产周转率(次)
zzzzt	string	总资产周转天数(天)
ldzz	string	流动资产周转率(次)
ldzzt	string	流动资产周转天数(天)
gdzz	string	股东权益周转率(次)
ldbl	string	流动比率
sdbl	string	速动比率
xjbl	string	现金比率(%)
lxzf	string	利息支付倍数
zjbl	string	长期债务与营运资金比率(%)
gdqy	string	股东权益比率(%)
cqfz	string	长期负债比率(%)
gdgd	string	股东权益与固定资产比率(%)
fzqy	string	负债与所有者权益比率(%)
zczjbl	string	长期资产与长期资金比率(%)
zblv	string	资本化比率(%)
gdzcjz	string	固定资产净值率(%)
zbgdh	string	资本固定化比率(%)
cqbl	string	产权比率(%)
qxjzb	string	清算价值比率(%)
gdzcbz	string	固定资产比重(%)
zcfzl	string	资产负债率(%)
zzc	string	总资产(元)
jyxj	string	经营现金净流量对销售收入比率(%)
zcjyxj	string	资产的经营现金流量回报率(%)
jylrb	string	经营现金净流量与净利润的比率(%)
jyfzl	string	经营现金净流量对负债比率(%)
xjlbl	string	现金流量比率(%)
dqgptz	string	短期股票投资(元)
dqzctz	string	短期债券投资(元)
dqjytz	string	短期其它经营性投资(元)
qcgptz	string	长期股票投资(元)
cqzqtz	string	长期债券投资(元)
cqjyxtz	string	长期其它经营性投资(元)
yszk1	string	1年以内应收帐款(元)
yszk12	string	1-2年以内应收帐款(元)
yszk23	string	2-3年以内应收帐款(元)
yszk3	string	3年以内应收帐款(元)
yfhk1	string	1年以内预付货款(元)
yfhk12	string	1-2年以内预付货款(元)
yfhk23	string	2-3年以内预付货款(元)
yfhk3	string	3年以内预付货款(元)
ysk1	string	1年以内其它应收款(元)
ysk12	string	1-2年以内其它应收款(元)
ysk23	string	2-3年以内其它应收款(元)
ysk3	string	3年以内其它应收款(元)
十大股东
API地址：https://api.zhituapi.cn/hs/gs/sdgd/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的十大股东数据。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
jzrq	string	截止日期yyyy-MM-dd
ggrq	string	公告日期yyyy-MM-dd
gdsm	string	股东说明
gdzs	number	股东总数
pjcg	number	平均持股(单位：股，按总股本计算)
sdgd	array<ZygdSdgd>	十大股东，其中ZygdSdgd对象见下方说明
十大流通股东
API地址：https://api.zhituapi.cn/hs/gs/ltgd/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的十大流通股东数据。按公告日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段说明
 
返回示例
 
Python接入
字段名称	数据类型	字段说明
jzrq	string	截止日期yyyy-MM-dd
ggrq	string	公告日期yyyy-MM-dd
sdgd	array<ZygdSdgd>	十大流通股东，其中ZygdSdgd对象见下方说明
股东变化趋势
API地址：https://api.zhituapi.cn/hs/gs/gdbh/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取上市公司的股东变化趋势数据。按截止日期倒序。

更新频率：每日03:30

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
jzrq	string	截止日期yyyy-MM-dd
gdhs	string	股东户数
bh	string	比上期变化情况


基金持股
API地址：https://api.zhituapi.cn/hs/gs/jjcg/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码获取该股票最近500家左右的基金持股情况。按截止日期倒序。

更新频率：每周六18:00

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

jzrq	string	截止日期yyyy-MM-dd
jjmc	string	基金名称
jjdm	string	基金代码
ccsl	number	持仓数量(股)
ltbl	number	占流通股比例(%)
cgsz	number	持股市值（元）
jzbl	number	占净值比例（%）

所属板块
API地址：https://api.zhituapi.cn/hs/gs/ssbk/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码作为参数，获取该股票的所属板块。

更新频率：每日21:00

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
keyword	string	关键字
content	string	内容，多个板块用空格隔开


经营范围
API地址：https://api.zhituapi.cn/hs/gs/jyfw/股票代码?token=token证书

描述：根据《股票列表》得到的股票代码作为参数，获取该股票的经营范围。

更新频率：每日21:00

请求频率限制：1分钟300次 | 包年版1分钟3千次 | 至尊版1分钟6千次

字段名称	数据类型	字段说明
keyword	string	关键字
content	string	内容
# Minimum Data Requirements

### 1. Current Registration & Exemption Lists

| Aspect           | Description                                                  |
| ---------------- | :----------------------------------------------------------- |
| URL              | [https://www.aemo.com.au/-/media/Files/Electricity/NEM/Participant_Information/NEM-Registration-and-Exemption-List.xls](https://www.aemo.com.au/-/media/Files/Electricity/NEM/Participant_Information/NEM-Registration-and-Exemption-List.xls) |
| File             | A `xls` file ([`NEM Registration and Exemption List.xls`](./GENERATORS/NEM%20Registration%20and%20Exemption%20List.xls)) |
| Content          | 11 sheets, one is [`Generators and Schedule Loads `](./GENERATORS/GENERATORS.md) |
| More Information | [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Participant-information/Current-participants/Current-registration-and-exemption-lists](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Participant-information/Current-participants/Current-registration-and-exemption-lists) |

### 2. Generator Bids

| Aspect           | Description                                                  |
| ---------------- | :----------------------------------------------------------- |
| Section          | `Bidmove_Summary`                                            |
| File Name        | `<#VISIBILITY_ID>_BIDMOVE_SUMMARY_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip` |
| Regex            | `PUBLIC_BIDMOVE_SUMMARY_<#CASE_DATE>_[0-9]{16}.zip`          |
| Example          | [http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip](http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_BIDMOVE_SUMMARY_20190428_0000000307275793.CSV](./BIDS/PUBLIC_BIDMOVE_SUMMARY_20190428_0000000307275793.CSV)) |
| Content          | Two parts:<br> 1. [`BIDDAYOFFER_D`](./BIDS/BIDDAYOFFER_D.pdf) (about 1047 rows) summarises generator bids per day<br> 2. **[`BIDPEROFFER_D`](./BIDS/BIDPEROFFER_D.pdf)** summarises generator bids per period |
| Update           | Daily shortly after 4am; 1 file per day                      |
| More Information | [https://www.nemweb.com.au/#bidmove-summary](https://www.nemweb.com.au/#bidmove-summary) |

### 3. 5-min predispatch)

Every 5 minutes AEMO updates a 60-minute look ahead of DISPATCH prices.

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `P5_Reports`                                                 |
| File Name        | `<#VISIBILITY_ID>_P5MIN_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip` |
| Regex            | `PUBLIC_P5MIN_<#CASE_DATE>[0-9]{4}_[0-9]{14}.zip`            |
| Example          | [http://nemweb.com.au/Reports/Current/P5_Reports/PUBLIC_P5MIN_201904301445_20190430144045.zip](http://nemweb.com.au/Reports/Current/P5_Reports/PUBLIC_P5MIN_201904301445_20190430144045.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_P5MIN_201904301430_20190430142545.CSV](./PRE_DISPATCH/PUBLIC_P5MIN_201904301430_20190430142545.CSV)) |
| Content          | Six parts:<br>1. [`P5MIN_CASESOLUTION`](./PRE_DISPATCH/P5MIN_CASESOLUTION.pdf)<br>2. [`P5MIN_LOCAL_PRICE`](./PRE_DISPATCH/P5MIN_LOCAL_PRICE.pdf)<br>3. [`P5MIN_REGIONSOLUTION`](./PRE_DISPATCH/P5MIN_REGIONSOLUTION.pdf)<br>4. [`P5MIN_INTERCONNECTORSOLN`](./PRE_DISPATCH/P5MIN_INTERCONNECTORSOLN.pdf)<br>5. [`P5MIN_CONSTRAINTSOLUTION`](./PRE_DISPATCH/P5MIN_CONSTRAINTSOLUTION.pdf)<br>6. [`P5MIN_BLOCKEDCONSTRAINT`](./PRE_DISPATCH/P5MIN_BLOCKEDCONSTRAINT.pdf) |
| Update           | Every 5 minutes, 288 files per day                           |
| More Information | https://www.nemweb.com.au/#p5-reports                        |

### 4. Pre-dispatch

The *pre-dispatch* period starts at the next *trading interval* and continues to include the next *trading day* with a half hour resolution. At the time of initial publication the *pre-dispatch* covers the remainder of the day, the next day and the first 4 hours of the following day.

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `PredispatchIS_Reports`                                      |
| File Name        | `<#VISIBILITY_ID>_PREDISPATCHIS_<#CASE_DATETIME>_<#REPORT_DATETIME>.zip` |
| Regex            | `PUBLIC_PREDISPATCHIS_<#CASE_DATE>[0-9]{4}_[0-9]{14}.zip`    |
| Example          | [http://nemweb.com.au/Reports/Current/PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_201905031130_20190503110120.zip](http://nemweb.com.au/Reports/Current/PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_201905031130_20190503110120.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_PREDISPATCHIS_201905031130_20190503110120.CSV](./PRE_DISPATCH/PUBLIC_PREDISPATCHIS_201905031130_20190503110120.CSV)) |
| Content          | 7 parts: <br>1. [`PREDISPATCHCASESOLUTION`](./PRE_DISPATCH/PREDISPATCHCASESOLUTION.pdf) <br>2. [`PREDISPATCH_LOCAL_PRICE`](./PRE_DISPATCH/PREDISPATCH_LOCAL_PRICE.pdf)<br>3. [`PREDISPATCHPRICE`](./PRE_DISPATCH/PREDISPATCHPRICE.pdf)<br>4. [`PREDISPATCHREGIONSUM`](./PRE_DISPATCH/PREDISPATCHREGIONSUM.pdf)<br>5. [`PREDISPATCHINTERCONNECTORRES`](./PRE_DISPATCH/PREDISPATCHINTERCONNECTORRES.pdf)<br>6. [`PREDISPATCHCONSTRAINT`](./PRE_DISPATCH/PREDISPATCHCONSTRAINT.pdf)<br>7. [`PREDISPATCHBLOCKEDCONSTRAINT`](./PRE_DISPATCH/PREDISPATCHBLOCKEDCONSTRAINT.pdf) |
| Update           | Every 30 minutes, 48 files per day                           |
| More Information | [https://www.nemweb.com.au/#predispatchis-reports](https://www.nemweb.com.au/#predispatchis-reports) |

### 5. Loss Factors

| Aspect  | Description                                                  |
| ------- | ------------------------------------------------------------ |
| URL     | https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Security-and-reliability/Loss-factor-and-regional-boundaries |
| File    | A `xlsx` file ( [2018-19 MLF Applicable from 01 July 2018 to 30 June 2019 - updated 11 July 2018.xlsx](./LOSS_FACTORS/2018-19%20MLF%20Applicable%20from%2001%20July%202018%20to%2030%20June%202019%20-%20updated%2011%20July%202018.xlsx)) |
| Content | Five sheets for five regions. Each sheet contains three parts: see [`LOSS_FACTORS`](./LOSS_FACTORS/LOSS_FACTORS.md)<br>1. Loads<br>2. Generators<br>3. Embedded Generators |
| Update  | Annually by 1 April                                          |

### 6. Network Outages

| Aspect    | Description                                                  |
| --------- | ------------------------------------------------------------ |
| Section   | `Network`                                                    |
| File Name | `<#VISIBILITY_ID>_NETWORK_<#REPORT_DATETIME>_<#EVENT_QUEUE_ID>.ZIP` |
| Regex     | `PUBLIC_NETWORK_<#CASE_DATE>[0-9]{6}_[0-9]{16}.zip`          |
| Example   | [http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip](http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip) |
| File      | A `csv` file after decompression (e.g. [PUBLIC_NETWORK_20190429133006_0000000307290523.CSV](./NETWORK/Network%20Outages/PUBLIC_NETWORK_20190429133006_0000000307290523.CSV)) |
| Content   | Two parts: <br>1. [`NETWORK_OUTAGECONSTRAINTSET`](./NETWORK/Network%20Outages/NETWORK_OUTAGECONSTRAINTSET.pdf) lists the Constraint Sets that are expected to be invoked for the outage once it is confirmed to proceed<br>2. [`NETWORK_OUTAGEDETAIL`](./NETWORK/Network%20Outages/NETWORK_OUTAGEDETAIL.pdf) lists asset owners planned outages for transmission equipment. |
| Update    | Every 30 minutes; 50 files per day                           |

### 7. Transmission Equipment Ratings

1. **`altlimits.zip`**: complete list of ratings used in AEMO's EMS (energy management system)

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| URL              | [http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip](http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip) |
| File             | A `csv` file ([`⁨./Eterra⁩/⁨habdata98⁩/⁨LimitData/altlimits.csv⁩`](./NETWORK/Transimission%20Equipment%20Ratings/Eterra/habdata98/LimitData/altlimits.csv)) |
| Content          | See [`ALTLIMITS`](./NETWORK/Transimission%20Equipment%20Ratings/ALTLIMITS.md) |
| Update           | When the network model is updated (normally every two weeks)<br>**Note:** Historical data is not available. |
| More Information | [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings) |

2. **`PUBLIC_TER_DAILY.zip`**: contains the ratings used in constraint equations and the ID used in the right-hand of the constraint equations

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| URL              | [http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip](http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip) |
| File             | A `csv` file ([⁨PUBLIC_TER_DAILY.CSV](./NETWORK/Transimission%20Equipment%20Ratings/PUBLIC_TER_DAILY.CSV)) |
| Content          | See [`LIM_ALTLIM`](./NETWORK/Transimission%20Equipment%20Ratings/LIM_ALTLIM.md) |
| Update           | On change (generally every few minutes)<br>Published on 8am everyday (not sure)<br>**Note:** Historical data is not available. |
| More Information | [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings) |

### 8. Market Price Cap

see [https://www.aemc.gov.au/news-centre/media-releases/aemc-publishes-schedule-reliability-settings-2018-19](https://www.aemc.gov.au/news-centre/media-releases/aemc-publishes-schedule-reliability-settings-2018-19)

| VALUES                     | 2017-18     | 2018-19         |
| -------------------------- | ----------- | --------------- |
| MARKET PRICE CAP           | $14,200/MWh | **$14,500/MWh** |
| CUMULATIVE PRICE THRESHOLD | $212,800    | $216,900        |

**updates** annually.

### 9. Interconnector Connectivity & Limits

[http://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Congestion-Information/2017/Interconnector-Capabilities.pdf](http://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Congestion-Information/2017/Interconnector-Capabilities.pdf) 

### 10. Dispatch Summary

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `DispatchIS_Reports`                                         |
| File Name        | `<#VISIBILITY_ID>_DISPATCHIS_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip` |
| Regex            | `PUBLIC_DISPATCHIS_<#CASE_DATE>[0-9]{4}_[0-9]{16}.zip`       |
| Example          | [http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip](http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip) |
| File             | A `csv` file (e.g. [PUBLIC_DISPATCHIS_201904301035_0000000307325047.CSV](./DISPATCH/PUBLIC_DISPATCHIS_201904301035_0000000307325047.CSV)) |
| Content          | Nine parts:<br>1. [`DISPATCHCASESOLUTION`](./DISPATCH/DISPATCHCASESOLUTION.pdf)<br>2. [`DISPATCH_LOCAL_PRICE`](./DISPATCH/DISPATCH_LOCAL_PRICE.pdf)<br>3. [`DISPATCHPRICE`](./DISPATCH/DISPATCHPRICE.pdf)<br>4. [`DISPATCHREGIONSUM`](./DISPATCH/DISPATCHREGIONSUM.pdf) <br>5. [`DISPATCHINTERCONNECTORRES`](./DISPATCH/DISPATCHINTERCONNECTORRES.pdf)<br>6. [`DISPATCH_MR_SCHEDULE_TRK`](./DISPATCH/DISPATCH_MR_SCHEDULE_TRK.pdf)<br>7. [`DISPATCHCONSTRAINT`](./DISPATCH/DISPATCHCONSTRAINT.pdf)<br>8. [`DISPATCHBLOCKEDCONSTRAINT`](./DISPATCH/DISPATCHBLOCKEDCONSTRAINT.pdf)<br>9. [`DISPATCH_INTERCONNECTION`](./DISPATCH/DISPATCH_INTERCONNECTION.pdf) |
| Update           | Every 5 minutes, 288 files per day                           |
| More Information | [https://www.nemweb.com.au/#dispatchis-reports](https://www.nemweb.com.au/#dispatchis-reports) |

### 11. Actual Generation and Load Data

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `Dispatch_SCADA`                                             |
| File Name        | `<#VISIBILITY_ID>_DISPATCHSCADA_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip` |
| Regex            | `PUBLIC_DISPATCHSCADA_<#CASE_DATE>[0-9]{4}_[0-9]{16}.zip`    |
| Example          | [http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip](http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.CSV](./ACTUAL_GENERATION%26LOAD_DATA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.CSV)) |
| Content          | See [`DISPATCH_UNIT_SCADA`](./ACTUAL_GENERATION%26LOAD_DATA/DISPATCH_UNIT_SCADA.pdf) |
| Update           | Every 5 minutes, 288 files per day                           |
| More Information | [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Market-Management-System-MMS/Generation-and-Load](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Market-Management-System-MMS/Generation-and-Load) |

### 12. Intermittent Generation Dispatch Forecasts

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `Next_Day_Intermittent_DS`                                   |
| File Name        | `<#VISIBILITY_ID>_NEXT_DAY_INTERMITTENT_DS_<#REPORT_DATETIME>.zip` |
| Regex            | `PUBLIC_NEXT_DAY_INTERMITTENT_DS_<#REPORT_DATE>[0-9]{6}.zip` |
| Example          | [http://nemweb.com.au/Reports/Current/Next_Day_Intermittent_DS/PUBLIC_NEXT_DAY_INTERMITTENT_DS_20190527041026.zip](http://nemweb.com.au/Reports/Current/Next_Day_Intermittent_DS/PUBLIC_NEXT_DAY_INTERMITTENT_DS_20190527041026.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_NEXT_DAY_INTERMITTENT_DS_20190527041026.CSV](./INTERMITTENT_GENERATION_DISPATCH_FORECASTS/PUBLIC_NEXT_DAY_INTERMITTENT_DS_20190527041026.CSV)) |
| Content          | See<br>1. [`INTERMITTENT_DS_RUN`](./INTERMITTENT_GENERATION_DISPATCH_FORECASTS/INTERMITTENT_DS_RUN.pdf)<br>2. [`INTERMITTENT_DS_PRED`](./INTERMITTENT_GENERATION_DISPATCH_FORECASTS/INTERMITTENT_DS_PRED.pdf)<br>3. [`INTERMITTENT_FORECAST_TRK`](./INTERMITTENT_GENERATION_DISPATCH_FORECASTS/INTERMITTENT_FORECAST_TRK.pdf) |
| Update           | 1 files per day, shortly after 4 am                          |
| More Information | 1. [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Planning-and-forecasting/Solar-and-wind-energy-forecasting](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Planning-and-forecasting/Solar-and-wind-energy-forecasting)<br>2. [Guide_to_Intermittent_Generation](./INTERMITTENT_GENERATION_DISPATCH_FORECASTS/Guide_to_Intermittent_Generation.pdf) |

### 13. Dispatch results for units

Dispatch data now Public from previous day. Targets for scheduled and semi-scheduled generating units.

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `Next_Day_Dispatch`                                          |
| File Name        | `<#VISIBILITY_ID>_NEXT_DAY_DISPATCH_<#CASE_DATE>_<#EVENT_QUEUE_ID>.zip` |
| Regex            | `PUBLIC_NEXT_DAY_DISPATCH_<#CASE_DATE>_[0-9]{16}.zip`        |
| Example          | [http://nemweb.com.au/Reports/Current/Next_Day_Dispatch/PUBLIC_NEXT_DAY_DISPATCH_20190527_0000000308408731.zip](http://nemweb.com.au/Reports/Current/Next_Day_Dispatch/PUBLIC_NEXT_DAY_DISPATCH_20190527_0000000308408731.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_NEXT_DAY_DISPATCH_20190527_0000000308408731.CSV](./DISPATCH_PUBLIC/PUBLIC_NEXT_DAY_DISPATCH_20190527_0000000308408731.CSV)) |
| Content          | Five parts:<br/>1. [`DISPATCHLOAD`](./DISPATCH_PUBLIC/DISPATCHLOAD.pdf)<br/>2. [`DISPATCH_LOCAL_PRICE`](./DISPATCH_PUBLIC/DISPATCH_LOCAL_PRICE.pdf)<br/>3. [`DISPATCHOFFERTRK`](./DISPATCH_PUBLIC/DISPATCHOFFERTRK.pdf)<br/> 4. [`DISPATCHCONSTRAINT`](./DISPATCH_PUBLIC/DISPATCHCONSTRAINT.pdf)<br/> 5. [`DISPATCH_MNSPBIDTRK`](./DISPATCH_PUBLIC/DISPATCH_MNSPBIDTRK.pdf) |
| Update           | 1 files per day, shortly after 4 am                          |
| More Information | [http://nemweb.com.au/#next-day-dispatch](http://nemweb.com.au/#next-day-dispatch) |

### 14. Trading

30 Minute Trading Interval Results

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Section          | `TradingIS_Reports`                                          |
| File Name        | `<#VISIBILITY_ID>_TRADINGIS_<#CASE_DATETIME>_<#EVENT_QUEUE_ID>.zip` |
| Regex            | `PUBLIC_TRADINGIS_<#CASE_DATETIME>_[0-9]{16}.zip`            |
| Example          | [http://nemweb.com.au/Reports/Current/TradingIS_Reports/PUBLIC_TRADINGIS_201907041130_0000000309915971.zip](http://nemweb.com.au/Reports/Current/TradingIS_Reports/PUBLIC_TRADINGIS_201907041130_0000000309915971.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_TRADINGIS_201907041130_0000000309915971.CSV](./TRADING/PUBLIC_TRADINGIS_201907041130_0000000309915971.CSV)) |
| Content          | Three parts: <br/>1. [TRADINGINTERCONNECT](./TRADING/TRADINGINTERCONNECT.pdf) <br/>2. [TRADINGPRICE](./TRADING/TRADINGPRICE.pdf)<br/>3. [TRADINGREGIONSUM](./TRADING/TRADINGREGIONSUM.pdf) |
| Update           | 1 file every 30 min, 48 files per day                        |
| More Information | [http://nemweb.com.au/#tradingis-reports](http://nemweb.com.au/#tradingis-reports) |
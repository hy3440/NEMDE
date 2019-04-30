# Minimum Data Requirements

### 1. Generator Bids

| Aspect  | Description                                                  |
| ------- | :----------------------------------------------------------- |
| URL     | [http://nemweb.com.au/Reports/Current/Bidmove_Summary/](http://nemweb.com.au/Reports/Current/Bidmove_Summary/) |
| Regex   | `PUBLIC_BIDMOVE_SUMMARY_([0-9]{8})_[0-9]{16}.zip`            |
| Example | [http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip](http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip) |
| File    | A `csv` file after decompression (e.g. [PUBLIC_BIDMOVE_SUMMARY_20190428_0000000307275793.CSV](./BIDS/PUBLIC_BIDMOVE_SUMMARY_20190428_0000000307275793.CSV)) |
| Content | Two parts:<br> 1. [`BIDDAYOFFER_D`](./BIDS/BIDDAYOFFER_D.pdf) (about 1047 rows) summarises generator bids per day<br> 2. **[`BIDPEROFFER_D`](./BIDS/BIDPEROFFER_D.pdf)** summarises generator bids per period |
| Update  | Daily shortly after 4am                                      |

### 2. Regional Load (5 min prediction)

| Aspect           | Description |
| ---------------- | ----------- |
| URL              |             |
| Regex            |             |
| Example          |             |
| File             |             |
| Content          |             |
| Update           |             |
| More Information |             |

### 3. Interconnector Connectivity & Limits

[http://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Congestion-Information/2017/Interconnector-Capabilities.pdf](http://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Congestion-Information/2017/Interconnector-Capabilities.pdf) 

### 4. Generator Ramp Rates

### 5. Loss Factors

| Aspect  | Description                                                  |
| ------- | ------------------------------------------------------------ |
| URL     | https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Security-and-reliability/Loss-factor-and-regional-boundaries |
| File    | A `xlsx` file ( [2018-19 MLF Applicable from 01 July 2018 to 30 June 2019 - updated 11 July 2018.xlsx](./LOSS_FACTORS/2018-19%20MLF%20Applicable%20from%2001%20July%202018%20to%2030%20June%202019%20-%20updated%2011%20July%202018.xlsx)) |
| Content | Five sheets for five regions. Each sheet contains three parts:<br>1. Loads: see below<br>2. Generators: see below<br>3. Embedded Generators: see below |
| Update  | Annually by 1 April                                          |

1. Loads:

| Name        | Data Type | Mandatory | Comment                                       |
| ----------- | --------- | --------- | --------------------------------------------- |
| Location    |           |           |                                               |
| Voltage(kV) |           |           |                                               |
| TNI         |           |           | Connection point Transmission Node Identifier |
| 2018-19 MLF |           |           | Present Margional Loss Factor                 |
| 2017-18 MLF |           |           | Former Margional Loss Factor                  |

2. Generators:

| Name                | Data Type | Mandatory | Comment                                       |
| ------------------- | --------- | --------- | --------------------------------------------- |
| Location            |           |           |                                               |
| Voltage(kV)         |           |           |                                               |
| DUID                |           |           | Dispatchable Unit Identifier                  |
| Connection Point ID |           |           |                                               |
| TNI                 |           |           | Connection point Transmission Node Identifier |
| 2018-19 MLF         |           |           | Present Margional Loss Factor                 |
| 2017-18 MLF         |           |           | Former Margional Loss Factor                  |

3. Embedded Generators: same as above

### 6. Market Price Cap

see [https://www.aemc.gov.au/news-centre/media-releases/aemc-publishes-schedule-reliability-settings-2018-19](https://www.aemc.gov.au/news-centre/media-releases/aemc-publishes-schedule-reliability-settings-2018-19)

| VALUES                     | 2017-18     | 2018-19         |
| -------------------------- | ----------- | --------------- |
| MARKET PRICE CAP           | $14,200/MWh | **$14,500/MWh** |
| CUMULATIVE PRICE THRESHOLD | $212,800    | $216,900        |

**updates** annually.

### 7. Actual Generation and Load Data

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| URL              | [http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/](http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/) |
| Regex            | `PUBLIC_DISPATCHSCADA_([0-9]{12})_[0-9]{16}.zip`             |
| Example          | [http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip](http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip) |
| File             | A `csv` file after decompression (e.g. [PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.CSV](./ACTUAL_GENERATION%26LOAD_DATA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.CSV)) |
| Content          | See [`DISPATCH_UNIT_SCADA`](./ACTUAL_GENERATION%26LOAD_DATA/DISPATCH_UNIT_SCADA.pdf) |
| Update           | Every five minutes.                                          |
| More Information | [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Market-Management-System-MMS/Generation-and-Load](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Market-Management-System-MMS/Generation-and-Load) |

### 8. Network Outages

| Aspect  | Description                                                  |
| ------- | ------------------------------------------------------------ |
| URL     | http://nemweb.com.au/Reports/Current/Network/](http://nemweb.com.au/Reports/Current/Network/) |
| Regex   | `PUBLIC_NETWORK_([0-9]{14})_[0-9]{16}.zip`                   |
| Example | [http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip](http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip) |
| File    | A `csv` file after decompression (e.g. [PUBLIC_NETWORK_20190429133006_0000000307290523.CSV](./NETWORK/Network%20Outages/PUBLIC_NETWORK_20190429133006_0000000307290523.CSV)) |
| Content | Two parts: <br>1. [`NETWORK_OUTAGECONSTRAINTSET`](./NETWORK/Network%20Outages/NETWORK_OUTAGECONSTRAINTSET.pdf) lists the Constraint Sets that are expected to be invoked for the outage once it is confirmed to proceed<br>2. [`NETWORK_OUTAGEDETAIL`](./NETWORK/Network%20Outages/NETWORK_OUTAGEDETAIL.pdf) lists asset owners planned outages for transmission equipment. |
| Update  | Every 30 minutes                                             |

### 9. [Transmission Equipment Ratings](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings)

1. **`altlimits.zip`**: complete list of ratings used in AEMO's EMS (energy management system)

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| URL              | [http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip](http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip) |
| File             | A `csv` file ([`⁨./Eterra⁩/⁨habdata98⁩/⁨LimitData/altlimits.csv⁩`](./NETWORK/Transimission%20Equipment%20Ratings/Eterra⁩/⁨habdata98⁩/⁨LimitData/altlimits.csv)) |
| Content          | See table below                                              |
| Update           | When the network model is updated (normally every two weeks) |
| More Information | [http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers) |

| Name            | Data Type   | Mandatory | Comment                                                      |
| --------------- | ----------- | :-------- | ------------------------------------------------------------ |
| Site Name       |             |           | The Substation, Terminal Station, or Power Station name      |
| Plant Type      | VARCHAR(10) |           | Transmission Lines may be Line, Tie, Summ for summated lines, or S_REACT for series reactors. Transformers may be Trans, Tx, or Tf. |
| Plant ID        | VARCHAR(20) |           | The equipment identifier                                     |
| Region          | VARCHAR(10) |           | The NEM region                                               |
| Measurement     |             |           | All values included in the publication process are MVA quantities |
| Level           |             |           | NORM, EMER, or LDSH as described in [Rating Application Levels](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Rating-Application-Levels) |
| Alternate Value |             |           | An identifier which describes when the rating is applicable, such as summer, winter, etc. Alternate Value application rules at the time of publication of this document are described in section 3 below. Note that any rating with an associated Alternate Value suffix of '_DYN' has a real time telemetered rating supplied by the asset owner. This telemetered value would normally be the rating applied in real time processes. If telemetered data is available, any associated static ratings will be used for predispatch, and for dispatch only on telemetered data failure. |
| Low             |             |           | The low and high provide a directional feature in the application of the rating. When associated with the Site Name, the Low and High are interpreted using the convention of : A positive value is power flow from the Site into the equipment. |
| High            |             |           | Same as above                                                |

2. **`PUBLIC_TER_DAILY.zip`**: contains the ratings used in constraint equations and the ID used in the right-hand of the constraint equations

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| URL              | [http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip](http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip) |
| File             | A `csv` file ([⁨PUBLIC_TER_DAILY.CSV](./NETWORK/⁨Transimission%20Equipment%20Ratings/PUBLIC_TER_DAILY.CSV)) |
| Content          | See table below                                              |
| Update           | On change (generally every few minutes)                      |
| More Information | [http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers) |

| Name            | Data Type   | Mandatory | Comment                                                      |
| --------------- | ----------- | :-------- | ------------------------------------------------------------ |
| SITE ID         |             |           | The Substation, Terminal Station, or Power Station name      |
| EQUIPMENT TYPE  | VARCHAR(10) |           | The type of equipment. Valid values are: LINE = Line  TRANS = Transformer
CB = Circuit breaker
ISOL = Isolator
CAP = Capacitor
REAC = Reactor
UNIT = Unit |
| EQUIPMENT ID    | VARCHAR(20) |           | The equipment identifier                                     |
| Region ID       | VARCHAR(10) |           | The NEM region                                               |
| RATING LEVEL    | VARCHAR(10) |           | NORM, EMER, or LDSH as described in [Rating Application Levels](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Rating-Application-Levels) |
| ALTERNATE VALUE |             |           | An identifier which describes when the rating is applicable, such as summer, winter, etc. Alternate Value application rules at the time of publication of this document are described in section 3 below. Note that any rating with an associated Alternate Value suffix of '_DYN' has a real time telemetered rating supplied by the asset owner. This telemetered value would normally be the rating applied in real time processes. If telemetered data is available, any associated static ratings will be used for predispatch, and for dispatch only on telemetered data failure. |
| RATING          |             |           | The rating value. Positive values indicate power flow from the site into the equipment. |
| RATING TYPE     |             |           | Either STATIC or DYNAMIC. Ratings with the Rating Type of DYNAMIC have a real time telemetered rating value supplied by the asset owner. This report does not include the telemetered rating value in the Rating field. The dynamic rating value would normally be the rating applied in Dispatch (and in some cases for a number of Pre-dispatch intervals). |
| SPD ID          | VARCHAR(21) |           | The identifier used in a constraint equation RHS to reference the rating value |
| EFFECTIVE FROM  | DATE        |           | The date and time the rating is active from and available as an input to constraint equations (inclusive) |
| EFFECTIVE TO    | DATE        |           | The date and time the rating is made inactive and unavailable as an input to constraint equations (exclusive) |

### 10. Dispatch Summary

| Aspect           | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| URL              | http://nemweb.com.au/Reports/Current/DispatchIS_Reports/     |
| Regex            | `PUBLIC_DISPATCHIS_([0-9]{12})_[0-9]{16}.zip`                |
| Example          | [http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip](http://nemweb.com.au/Reports/Current/DispatchIS_Reports/PUBLIC_DISPATCHIS_201904301040_0000000307325261.zip) |
| File             | A `csv` file (e.g. [PUBLIC_DISPATCHIS_201904301035_0000000307325047.CSV](./DISPATCH/PUBLIC_DISPATCHIS_201904301035_0000000307325047.CSV)) |
| Content          |                                                              |
| Update           |                                                              |
| More Information |                                                              |
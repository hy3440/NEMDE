# ALTLIMITS

More information: [http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers)

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
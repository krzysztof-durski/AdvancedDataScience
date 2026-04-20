# Data: Diagnoses and Procedures

## Goal

Get data from the German Healthcare system.

## Diagnoses

The **ICD System** is a classification of all medical conditions that hospitals in Germany might diagnose.
The data is public. Retrieve the dataset and make sure you can read it.

- go to [www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html](https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html)
- go to the **ICD-10-GM** section
- look for **Alphabet EDV-Fassung TXT (CSV)**
- download the zipfile
- unzip it

The file should contain entries for diagnoses with ICD-codes (e.g. `F14.1`) and their description e.g:

```text
1|2645|1|F14.1||||Schädlicher Gebrauch von Kokain
1|2650|1|F14.2||||Abhängigkeit von Kokain
1|2651|1|F14.2||||Abhängigkeit von Kokainderivat
```

Note that sometimes, codes also occur in later columns. For now, we are not interested in these:

```text
2|68638|1|A18.3+|K93.0*|||Tuberkulöse Appendizitis
```

Ignore the rows that do not have a code. These are synonyms.

> **Hint:** The moment you see `"Tuberkulöse Appendizitis"` in a file, a warning light should flash up in your head. Why?

## Procedures

The **OPS System** is a similar classification of medical procedures. They are crucial for hospitals to bill the health insurances.
The data is also available on the same page. Follow a similar procedure as above to obtain a text file of OPS-codes (e.g. `5-868.0`) and their descriptions:

```text
1|20906|5-868.0||Trennung von siamesischen Zwillingen
```

or

```text
1|6120|8-200.2#||Geschlossene Reposition einer Fraktur am Humerusschaft ohne Osteosynthese
1|8123|8-200.3#||Geschlossene Reposition einer Fraktur am distalen Humerus ohne Osteosynthese
1|6122|8-200.4#||Geschlossene Reposition einer Fraktur am proximalen Radius ohne Osteosynthese
```

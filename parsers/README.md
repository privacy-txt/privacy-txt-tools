# Parsers


### Description
This tool can be used to convert gdpr.txt files into a sqlite3 database file, and convert sqlite3 database files to gdpr.txt files. The files created by the data-collector tool are suitable for this parsing. 


### Installation
[Python3](https://www.python.org/) should be installed on the system. 

### Usage
To convert a gdprtxt db file to a gdpr.txt file, make sure the database file is present on the system and run the following command:

```
python3 db_to_txt.py -i <input.db> -o <output.txt>
```

To convert a gdpr.txt file to a gdprtxt db file, first create a database running the following command: 

``` bash
$sqlite3 output.db < gdprtxt_crawler.sql 
```

And then convert the gdpr.txt file to a database with the following command: 

```
python3 txt_to_db.py -i <input.txt> -o <output.db>
```


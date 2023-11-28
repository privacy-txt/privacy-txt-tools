# Cookie Compare


### Description
This tool can be used to compare to gdpr.txt db files by record and find missing / different cookies. For each cookie, the following is compared: 
- Unique pair of cookie name / site domain 
- Cookie duration in days 
- Third party value
- Optional value 
- Httponly value
- Secure value 

The output file saved in results/output.json by default, and is structured as following: 
- Matched (by unique pair cookie name / site domain) cookies with possible unmatched attributes
- Unmatched cookies from first argument file
- Unmatched cookies from second argument file

### Dataset
- Top 50 websites for NL are taken from [Similarweb](https://www.similarweb.com/top-websites/netherlands/) \[0\]
- The databases contained are cookies of the Top 50 websites for NL under different circumstances. 

### Installation
[Python3](https://www.python.org/) should be installed on the system. The necessary packages can be found in the `analyse/requirements.txt` file and installed using [pip](https://github.com/pypa/pip):
```bash
pip3 install -r analyse/requirements.txt
```

### Usage
To start scanning, make sure the gdprtxt db files are present on the system and then run the following command:
```
python3 main.py -i <file1.db> <file2.db>
```

### References
\[0\]: Similarweb, Similarweb - Top Websites. https://www.similarweb.com/top-websites/netherlands/, 2023.

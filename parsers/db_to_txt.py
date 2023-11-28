import sqlite3
import argparse
import os
import re


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    if not os.path.isfile(db_file):
        print("Input file does not exist")
        exit()

    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)

    return conn

parser = argparse.ArgumentParser(
    description='Convert db to gdpr.txt file'
)

parser.add_argument(
    "-i",
    "--input",
    required=True,
    help="Input file with a list of domains."
)
parser.add_argument("-o", "--output", required=True, help="Output db file.")
args = vars(parser.parse_args())


conn = create_connection(os.path.abspath(args["input"]))
c = conn.cursor()

f = open(args["output"], "w")

c.execute('SELECT SITE_DOMAIN FROM gdprtxt_banner LIMIT 1')

for row in c:
    f.write('# ' + re.compile(r"https?://(www\.)?").sub('', row[0]).strip().strip('/') + '\n')

f.write("# \n")
f.write("# Cookies \n")

c.execute('SELECT * FROM gdprtxt')
for row in c:
    f.write(row[1] + ', ' + row[2] + ', ' + str(row[3]) + ', ' +
            str(row[4]) + ', ' + str(row[5]) + ', ' + str(row[6]) + '\n')

f.write("# Banner \n")

c.execute('SELECT * FROM gdprtxt_banner')

for row in c:
    f.write(row[0] + ', ' + str(row[1]) + '\n')

f.write("# Privacy Policy \n")

c.execute('SELECT * FROM gdprtxt_privacypolicy')

for row in c:
    f.write(row[1])

f.close()
conn.close()










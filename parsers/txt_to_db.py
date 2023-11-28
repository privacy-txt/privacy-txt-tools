import sqlite3
import argparse
import os
import codecs


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


conn = create_connection(os.path.abspath(args["output"]))


with codecs.open(args["input"], "r", encoding='utf-8', errors='ignore') as f:
    for line in f:
        if len(line.split(', ')) == 3:
            hostname = line.split(', ')[0]

with codecs.open(args["input"], "r", encoding='utf-8', errors='ignore') as f:
    for line in f:
        if not line.startswith('#'):
            line=line[:-1]
            words = line.split(", ")
            if len(words) == 7:
                insert_stmt = "INSERT OR REPLACE INTO gdprtxt (SITE_DOMAIN, COOKIE_NAME, COOKIE_DOMAIN, DURATION, THIRD_PARTY, OPTIONAL, HTTPONLY, SECURE) VALUES (?, ?, ?, ?, ?, ?, ?, ? );"
                c = conn.cursor()
                try:
                    c.execute(insert_stmt, (hostname, words[0], words[1], words[2], words[3], words[4], words[5], words[6]))
                    # Save (commit) the changes
                    conn.commit()
                    if (c.rowcount > 0):
                        sql_rows = c.rowcount
                except sqlite3.OperationalError as err:
                    print(err)
                    print(insert_stmt)
                    print(hostname, words[0], words[1], words[2], words[3], words[4], words[5], words[6])
            if len(words) == 2:
                insert_stmt = "INSERT OR REPLACE INTO gdprtxt_banner (SITE_DOMAIN, BANNER) VALUES (?, ?);"
                c = conn.cursor()
                try:
                    c.execute(insert_stmt,
                              (hostname, words[0]))
                    # Save (commit) the changes
                    conn.commit()
                    if (c.rowcount > 0):
                        sql_rows = c.rowcount
                except sqlite3.OperationalError as err:
                    print(err)
                    print(insert_stmt)
                    print(hostname, words[0])
            if len(words) == 1:
                insert_stmt = "INSERT OR REPLACE INTO gdprtxt_privacypolicy (SITE_DOMAIN, LOCATION) VALUES (?, ?);"
                c = conn.cursor()
                try:
                    c.execute(insert_stmt,
                              (hostname, words[0]))
                    # Save (commit) the changes
                    conn.commit()
                    if (c.rowcount > 0):
                        sql_rows = c.rowcount
                except sqlite3.OperationalError as err:
                    print(err)
                    print(insert_stmt)
                    print(hostname, words[0])


f.close()
conn.close()

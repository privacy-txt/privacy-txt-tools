import sqlite3
import argparse
import os
import tldextract
import json


# establish database connection
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
    description='Compare cookies from two databases'
)

parser.add_argument(
    "-i",
    "--input",
    required=True,
    help="Input file with a list of domains.",
    type=argparse.FileType('r'),
    nargs='+'
)
args = vars(parser.parse_args())

# database connections vars
conn = []
cursor = []

# cookie records
cookies = []
cookie_domains = []
records = []
site_domains = []
i = 0

# get necessary data from databases
for file in args["input"]:
    conn.append(create_connection(file.name))
    cursor.append(conn[i].cursor())
    cursor[i].execute("SELECT * from gdprtxt ORDER BY SITE_DOMAIN, COOKIE_NAME")
    records.append(cursor[i].fetchall())
    cursor[i].execute("SELECT COOKIE_NAME from gdprtxt ORDER BY SITE_DOMAIN, COOKIE_NAME")
    cookies.append(cursor[i].fetchall())
    cursor[i].execute("SELECT COOKIE_DOMAIN from gdprtxt ORDER BY SITE_DOMAIN, COOKIE_NAME")
    cookie_domains.append(cursor[i].fetchall())
    k = 0
    for domain in cookie_domains[i]:
        cookie_domains[i][k] = tldextract.extract(domain[0]).domain
        k += 1
    cursor[i].execute("SELECT SITE_DOMAIN from gdprtxt ORDER BY SITE_DOMAIN")
    site_domains.append(cursor[i].fetchall())
    cookies[i] = [', '.join([''.join(j) for j in k]) for k in list(zip(cookies[i], cookie_domains[i], site_domains[i]))]
    i += 1


# initiate arrays for output
i, j, k, l = 0, 0, 0, 0
unmatched_domain = ""
matched0 = [str(args["input"][0].name) + " / " + records[0][0][8], {}]  # {t: {"matched": False} for t in names[0]}
matched1 = [str(args["input"][1].name) + " / " + records[1][0][8], {}]  # dict.fromkeys(names[1], False)
for db in site_domains:
    for site in db:
        if k == 0:
            if site[0] not in matched0[1]:
                matched0[1][site[0]] = {}
            matched0[1][site[0]][cookies[0][l]] = {'matched': False}
        else:
            if site[0] not in matched1[1]:
                matched1[1][site[0]] = {}
            matched1[1][site[0]][cookies[1][l]] = False

        l += 1
    l = 0
    k += 1

dur_change = 0
tp_change = 0
opt_change = 0
ho_change = 0
sec_change = 0

# match cookies and find differences

for name0 in cookies[0]:
    for name1 in cookies[1]:
        if not matched1[1][site_domains[1][i][0]][name1]:
            if name0 == name1:
                matched0[1][site_domains[0][j][0]][name0]["matched"] = True
                matched1[1][site_domains[1][i][0]][name1] = True
                if (((int(records[0][j][3]) <= 0) != (int(records[1][i][3]) <= 0))
                    or ((int(records[0][j][3]) - int(records[1][i][3])) > 1)
                    or ((int(records[1][i][3]) - int(records[0][j][3])) > 1)) \
                        and (int(records[1][k][3]) > 1.0 and int(records[0][j][3]) > 1.0):
                    matched0[1][site_domains[0][j][0]][name0]["duration"] = {args["input"][0].name: records[0][j][3],
                                                                             args["input"][1].name: records[1][i][3]}
                    dur_change += 1
                if records[0][j][4] != records[1][i][4]:
                    print(records[0][j] , records[1][i], name0, name1)
                    matched0[1][site_domains[0][j][0]][name0]["third_party"] = {args["input"][0].name: records[0][j][4],
                                                                                args["input"][1].name: records[1][i][4]}
                    tp_change += 1
                if records[0][j][5] != records[1][i][5]:
                    matched0[1][site_domains[0][j][0]][name0]["optional"] = {args["input"][0].name: records[0][j][5],
                                                                             args["input"][1].name: records[1][i][5]}
                    opt_change += 1
                if records[0][j][6] != records[1][i][6]:
                    matched0[1][site_domains[0][j][0]][name0]["httponly"] = {args["input"][0].name: records[0][j][6],
                                                                             args["input"][1].name: records[1][i][6]}
                    ho_change += 1
                if records[0][j][7] != records[1][i][7]:
                    matched0[1][site_domains[0][j][0]][name0]["secure"] = {args["input"][0].name: records[0][j][7],
                                                                           args["input"][1].name: records[1][i][7]}
                    sec_change += 1
                break
        i += 1
    i = 0
    j += 1

# create list of all non-matched cookies from file 1
unique_domains = set([item[0] for sublist in site_domains for item in sublist])
non_matched = {k: [] for k in unique_domains}
total_cookies0 = 0
unmatched_cookies = {}
for domain in unique_domains:
    if domain in matched0[1]:
        for item in list(matched0[1][domain]):
            total_cookies0 += 1
            if not matched0[1][domain][item]["matched"]:
                non_matched[domain].append(item)
                matched0[1][domain].pop(item)
                if not domain in unmatched_cookies:
                    unmatched_cookies[domain] = 1
                else:
                    unmatched_cookies[domain] += 1

# create list of all non-matched cookies from file 2
total_cookies1 = 0
for domain in list(matched1[1]):
    for item in list(matched1[1][domain]):
        total_cookies1 += 1
        if matched1[1][domain][item]:
            matched1[1][domain].pop(item)
        else:
            if not domain in unmatched_cookies:
                unmatched_cookies[domain] = 1
            else:
                unmatched_cookies[domain] += 1


matched0.append({"unmatched cookies from file 1": non_matched})
matched0.append({"unmatched cookies from file 2": matched1})

unmatched_total0 = 0
unmatched_total1 = 0
unmatched_sites = []
for i in non_matched:
    unmatched_total0 += len(non_matched[i])
    if non_matched[i]:
        unmatched_sites.append(i)
for i in matched1[1]:
    unmatched_total1 += len(matched1[1][i])
    if matched1[1][i]:
        unmatched_sites.append(i)

print("Total number of unmatched cookies:", unmatched_total0 + unmatched_total1, "\n"
        "\t", args["input"][0].name + ":",
        unmatched_total0, "/", total_cookies0, "\n"
        "\t", args["input"][1].name + ":", unmatched_total1, "/", total_cookies1
      )
print("Number of websites with unmatched cookies:", len(set(unmatched_sites)), "/", len(unique_domains))

print("Top 5 websites with most unmatched cookies:", *sorted(unmatched_cookies.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t')


print("Changes in matched cookies: \n "
      "\t duration:", dur_change, "\n"
                                  "\t third party:", tp_change, "\n"
                                                                "\t optional:", opt_change, "\n"
                                                                                            "\t http only:", ho_change,
      "\n"
      "\t secure:", sec_change)

conn[0].close()
conn[1].close()

with open("./results/output.json", "w") as file:
    json.dump(matched0, file, indent=2)

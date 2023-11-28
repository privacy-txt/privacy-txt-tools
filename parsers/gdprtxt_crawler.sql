BEGIN TRANSACTION;

DROP TABLE IF EXISTS gdprtxt;

CREATE TABLE gdprtxt(
       SITE_DOMAIN                  TEXT    NOT NULL,
       COOKIE_NAME	             TEXT    NOT NULL,
       COOKIE_DOMAIN		     TEXT    NOT NULL,
       DURATION	             FLOAT    NOT NULL,
       THIRD_PARTY                  BOOL    NOT NULL,
       OPTIONAL                     BOOL    NOT NULL,
       HTTPONLY			    BOOL    NOT NULL,
       SECURE                	     BOOL    NOT NULL,
       UPDATED                      DATE    DEFAULT (datetime('now','utc')),
    PRIMARY KEY (SITE_DOMAIN,COOKIE_NAME,COOKIE_DOMAIN)
);

DROP TABLE IF EXISTS gdprtxt_banner;

CREATE TABLE gdprtxt_banner(
       SITE_DOMAIN                  TEXT    NOT NULL,
       BANNER			     BOOL    NOT NULL,
       CMP		     TEXT    NOT NULL,
       UPDATED                      DATE    DEFAULT (datetime('now','utc')),
    PRIMARY KEY (SITE_DOMAIN)
);

DROP TABLE IF EXISTS gdprtxt_privacypolicy;

CREATE TABLE gdprtxt_privacypolicy(
       SITE_DOMAIN                  TEXT    NOT NULL,
       LOCATION		     TEXT    NOT NULL,
       UPDATED                      DATE    DEFAULT (datetime('now','utc')),
    PRIMARY KEY (SITE_DOMAIN)
);


COMMIT;

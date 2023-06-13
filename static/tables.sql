CREATE TABLE portfolios (
    PersonID INTEGER,
    companyName TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC NOT NULL,
    shares INTEGER

);

CREATE TABLE transactions (
    TransactionID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    PersonID INTEGER,
    TransactionType TEXT NOT NULL,
    companyName TEXT NOT NULL,
    symbol TEXT NOT NULL,
    price NUMERIC NOT NULL,
    shares INTEGER,
    OrderDate DateTime

);
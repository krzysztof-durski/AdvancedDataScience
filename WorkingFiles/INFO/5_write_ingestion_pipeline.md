# Write an Ingestion Pipeline

## Goal

Write a program that reads data from flat files into a database.

## Steps

- choose a database. This could be a SQL or a NoSQL database. For an easy start, I recommend DuckDB or MongoDB.
- decide for an ingestion strategy.
- consider what would happen if you had a lot more data (100x or 1000x the amount of data)
- implement the ingestion code using a programming language of your choice
- implement the test cases below using an automated test framework. It is not necessary that the ingestion solves all problems perfectly, but it should have **defined behavior**
- document your design decisions in a paragraph or bullet points

## Pick a database

Decide which database system you want to use. I recommend either **MongoDB**, **PostGres** or **DuckDB**.
I recommend starting the first two locally using Docker.
DuckDB can be imported as a Python Library and is installable by `pip` or `uv`.

> **Hint:** If you want to focus on the database part of the project rather than the data analysis, consider using two databases and creating an ETL job and copy a subset of the data from one DB to the other. This sounds boring but it is actually one of the most important skills in the field.

## Write the ingestion program

Write a program that ingests the data into a database. Some questions to consider:

- should the program run as a one-off script or should there be multiple runs necessary?
- what should happen when an error occurs?
- what should happen when someone runs the ingestion again?
- what configuration options should the program have?

> **Hint:** There might be very specific requirements on these questions in any real-world project.
> Since this is a study project, you are free to make assumptions and document them.

## Test Cases

In all tests, start with an empty database. After the ingestion, check the number of entries in the database.

- load entries from a single file
- load non-overlapping entries from two files
- load entries from a single file with a corrupted entry
- load entries from a single file with a duplicate entry
- load entries from two overlapping files
- load entries from a single file. Then load the same file again
- load entries from two files that have the same entries, but different values
- load entries from one file. Then load entries from a second, bigger file that contains all entries of the first

## Hints

- before writing the tests, create test data (a series of input files with 10 entries)
- consider running the database in a Docker container
- consider switching off index updates in the database during the ingestion
- if you use Python, consider generator functions for processing entries

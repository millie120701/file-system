import mysql.connector
from mysql.connector import Error
from datetime import date

def create_db_connection(host_name, user_name, pw, db):
    conn = None
    try:
        conn = mysql.connector.connect(
            host= host_name,
            user= user_name,
            password=pw,
            database= db
        )
    except Error as err:
        print(f"Error: '{err}'")

    return conn

connection = create_db_connection("127.0.0.1", "root", "78787890Hi!", "FileSystem")

mycursor = connection.cursor()
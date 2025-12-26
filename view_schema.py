"""Quick script to view SQLite database schema"""
import sqlite3

# Connect to database
conn = sqlite3.connect('local.db')
cursor = conn.cursor()

# Get table schema
print("=" * 60)
print("MESSAGES TABLE SCHEMA")
print("=" * 60)
schema = cursor.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'"
).fetchone()
if schema:
    print(schema[0])
else:
    print("Table not created yet")

# Get indexes
print("\n" + "=" * 60)
print("INDEXES")
print("=" * 60)
indexes = cursor.execute(
    "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='messages' AND sql IS NOT NULL"
).fetchall()
if indexes:
    for idx in indexes:
        print(idx[0])
else:
    print("No indexes yet")

# Get table info (columns with types)
print("\n" + "=" * 60)
print("COLUMN DETAILS")
print("=" * 60)
table_info = cursor.execute("PRAGMA table_info(messages)").fetchall()
if table_info:
    print(f"{'CID':<5} {'Name':<15} {'Type':<10} {'NotNull':<10} {'Default':<10} {'PK':<5}")
    print("-" * 60)
    for col in table_info:
        print(f"{col[0]:<5} {col[1]:<15} {col[2]:<10} {col[3]:<10} {str(col[4]):<10} {col[5]:<5}")
else:
    print("Table not created yet")

# Get row count
print("\n" + "=" * 60)
print("DATA SUMMARY")
print("=" * 60)
try:
    count = cursor.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    print(f"Total messages: {count}")
    
    if count > 0:
        # Show sample data
        print("\nSample rows (first 5):")
        samples = cursor.execute("SELECT * FROM messages LIMIT 5").fetchall()
        for row in samples:
            print(f"  {row}")
except:
    print("Table not accessible yet")

conn.close()

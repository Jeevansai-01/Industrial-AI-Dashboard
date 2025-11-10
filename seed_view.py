import argparse   
import sqlite3   

def fetch_rows(limit=10, order="desc", min_temp=None, max_temp=None):
    """
    Fetch rows from the readings table with optional temperature filters.
    limit: number of rows to return.
    order: 'asc' (oldest first) or 'desc' (newest first).
    min_temp/max_temp: numeric thresholds for temperature filter.
    """
    # Validate order keyword to avoid SQL injection; only allow specific strings.
    order_sql = "DESC" if str(order).lower() == "desc" else "ASC"  

    # Build base SQL with placeholders for filters.
    sql = f"""
        SELECT id, timestamp, temperature, pressure, motor_speed
        FROM readings
        WHERE 1=1
    """   

    params = []   

    # Add temperature lower bound if provided.
    if min_temp is not None:
        sql += " AND temperature >= ?"
        params.append(float(min_temp))  # Ensure numeric type. 

    # Add temperature upper bound if provided.
    if max_temp is not None:
        sql += " AND temperature <= ?"
        params.append(float(max_temp))  # Ensure numeric type. 

    # Append ORDER BY and LIMIT using validated order and integer limit.
    sql += f" ORDER BY id {order_sql} LIMIT ?"
    params.append(int(limit))  # Final positional parameter is the limit. 

    with sqlite3.connect("sensor_data.db") as conn:  # Open the DB file. 
        cur = conn.cursor()  # Create a cursor to execute SQL. 
        cur.execute(sql, params)  # Execute with bound parameters. 
        rows = cur.fetchall()  # Read all returned rows. 

    return rows  

def main():
    # Set up CLI options with argparse.
    parser = argparse.ArgumentParser(description="View rows from SQLite 'readings' table")  # Help text. 
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to show (default: 10)")  # Count. 
    parser.add_argument("--order", choices=["asc", "desc"], default="desc", help="Sort by id asc/desc")  # Direction. 
    parser.add_argument("--min-temp", type=float, help="Filter: temperature >= this value")  # Lower filter. 
    parser.add_argument("--max-temp", type=float, help="Filter: temperature <= this value")  # Upper filter. 

    args = parser.parse_args()   

    
    rows = fetch_rows(limit=args.limit, order=args.order, min_temp=args.min_temp, max_temp=args.max_temp)   

   
    if not rows:  
        print("No rows found.")  
        return

    
    print(f"{'id':>5}  {'timestamp':<20}  {'temp':>7}  {'press':>7}  {'rpm':>8}")  
    print("-" * 56)   

    for r in rows:  
        rid, timestamp, temp, press, rpm = r   
        print(f"{rid:5d}  {timestamp:<20}  {temp:7.2f}  {press:7.2f}  {rpm:8.2f}")  

if __name__ == "__main__":
    main()  

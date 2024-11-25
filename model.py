import psycopg2
import psycopg2.extras
from psycopg2 import sql

class Model:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname='electronic-car-database',
            user='postgres',
            password='1234',
            host='localhost',
            port=5432
        )
        self.conn.autocommit = True


class BaseModel(Model):
    table_name = ''
    pk = ''
    columns = []

    def __init__(self):
        super().__init__()

    def create(self, data):
        placeholders = ', '.join(['%s'] * len(data))
        cols = ', '.join(data.keys())
        query = f"INSERT INTO {self.table_name} ({cols}) VALUES ({placeholders}) RETURNING {self.pk}"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, list(data.values()))
                self.conn.commit()
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error inserting into {self.table_name}: {e}")
            self.conn.rollback()

    def read_all(self):
        query = f"SELECT * FROM {self.table_name} LIMIT 100"
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error reading from {self.table_name}: {e}")

    def update(self, pk_value, data):
        set_clause = ', '.join([f"{col}=%s" for col in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.pk}=%s"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, list(data.values()) + [pk_value])
                self.conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Error updating {self.table_name}: {e}")
            self.conn.rollback()

    def delete(self, pk_value):
        query = f"DELETE FROM {self.table_name} WHERE {self.pk}=%s"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (pk_value,))
                self.conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Error deleting from {self.table_name}: {e}")
            self.conn.rollback()

    def read_by_pk(self, pk_value):
        query = f"SELECT * FROM {self.table_name} WHERE {self.pk}=%s"
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query, (pk_value,))
                return cursor.fetchone()
        except Exception as e:
            print(f"Error reading from {self.table_name}: {e}")

    def validate_data(self, data):
        # Implement in child classes
        return True, None
    
    def generate_data(self, num_rows):
        """
        Generate random data for the table using SQL functions,
        handling various data types and foreign keys.
        """
        try:
            cursor = self.conn.cursor()

            # Get the list of columns excluding the primary key
            columns = self.columns.copy()
            if self.pk in columns:
                columns.remove(self.pk)

            # Retrieve data types for each column
            data_types = []
            for column in columns:
                cursor.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name=%s AND column_name=%s
                """, [self.table_name, column])
                data_type = cursor.fetchone()[0]
                data_types.append(data_type)

            # Identify foreign key relationships
            foreign_keys = {}
            for column in columns:
                cursor.execute("""
                    SELECT 
                        tc.constraint_name, 
                        kcu.column_name AS fk_column, 
                        ccu.table_name AS foreign_table, 
                        ccu.column_name AS foreign_column
                    FROM 
                        information_schema.table_constraints AS tc 
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                    WHERE 
                        tc.constraint_type = 'FOREIGN KEY' 
                        AND tc.table_name = %s 
                        AND kcu.column_name = %s
                """, [self.table_name, column])
                fk_info = cursor.fetchone()
                if fk_info:
                    foreign_keys[column] = {
                        'foreign_table': fk_info[2],
                        'foreign_column': fk_info[3]
                    }

            # Generate and execute INSERT statements for the specified number of rows
            for _ in range(num_rows):
                # Build value expressions for each column
                value_expressions = []
                for column, data_type in zip(columns, data_types):
                    if column in foreign_keys:
                        # For foreign keys, select a random existing value from the foreign table
                        fk_table = foreign_keys[column]['foreign_table']
                        fk_column = foreign_keys[column]['foreign_column']
                        value_expr = sql.SQL("(SELECT {fk_column} FROM {fk_table} ORDER BY RANDOM() LIMIT 1)").format(
                            fk_column=sql.Identifier(fk_column),
                            fk_table=sql.Identifier(fk_table)
                        )
                    else:
                        # Generate random data based on data type using SQL functions
                        if data_type == 'integer':
                            value_expr = sql.SQL('TRUNC(RANDOM() * 1000)::INTEGER')
                        elif data_type == 'character varying':
                            value_expr = sql.SQL("LEFT(MD5(RANDOM()::TEXT), 10)")
                        elif data_type == 'text':
                            value_expr = sql.SQL("LEFT(MD5(RANDOM()::TEXT), 20)")
                        elif data_type == 'date':
                            value_expr = sql.SQL("DATE '2024-01-01' + (RANDOM() * 365)::INT")
                        elif data_type == 'boolean':
                            value_expr = sql.SQL("(RANDOM() < 0.5)")
                        elif data_type in ('double precision', 'numeric'):
                            value_expr = sql.SQL("(RANDOM() * 1000)")
                        elif data_type.startswith('timestamp'):
                            value_expr = sql.SQL("TIMESTAMP '2024-01-01 00:00:00' + (RANDOM() * INTERVAL '365 days')")
                        else:
                            value_expr = sql.SQL('NULL')
                    value_expressions.append(value_expr)

                # Build the INSERT query using psycopg2.sql to safely include identifiers
                insert_query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({values})").format(
                    table=sql.Identifier(self.table_name),
                    fields=sql.SQL(', ').join(map(sql.Identifier, columns)),
                    values=sql.SQL(', ').join(value_expressions)
                )
                # Execute the INSERT query
                cursor.execute(insert_query)

            # Commit the transaction
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error generating data for {self.table_name}: {e}")
            self.conn.rollback()
            return False


class Car(BaseModel):
    table_name = 'car'
    pk = 'carid'
    columns = ['make', 'model', 'year', 'vin', 'ownerid']

    def validate_data(self, data):
        errors = []
        if 'year' in data:
            if not isinstance(data['year'], int):
                errors.append('Year must be an integer.')
        if 'ownerid' in data:
            if data['ownerid'] is not None:
                owner = Owner()
                owner_data = owner.read_by_pk(data['ownerid'])
                if not owner_data:
                    errors.append(f"Owner with ID {data['ownerid']} does not exist.")
        return len(errors) == 0, errors


class Owner(BaseModel):
    table_name = 'owner'
    pk = 'ownerid'
    columns = ['firstname', 'lastname', 'phone', 'email']

    def validate_data(self, data):
        # Add validation if needed
        return True, None


class Mechanic(BaseModel):
    table_name = 'mechanic'
    pk = 'mechanicid'
    columns = ['name', 'specialty', 'phone']

    def validate_data(self, data):
        # Add validation if needed
        return True, None


class ServiceRecord(BaseModel):
    table_name = 'servicerecord'
    pk = 'serviceid'
    columns = ['carid', 'servicedate', 'servicetype', 'servicecost']

    def validate_data(self, data):
        errors = []
        if 'carid' in data:
            car = Car()
            car_data = car.read_by_pk(data['carid'])
            if not car_data:
                errors.append(f"Car with ID {data['carid']} does not exist.")
        return len(errors) == 0, errors


class ServiceMechanic(BaseModel):
    table_name = 'servicemechanic'
    pk = ''
    columns = ['serviceid', 'mechanicid', 'hoursworked']

    def create(self, data):
        placeholders = ', '.join(['%s'] * len(data))
        cols = ', '.join(self.columns)
        query = f"INSERT INTO {self.table_name} ({cols}) VALUES ({placeholders})"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, list(data.values()))
                self.conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Error inserting into {self.table_name}: {e}")
            self.conn.rollback()

    def read_all(self):
        query = f"SELECT * FROM {self.table_name}"
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error reading from {self.table_name}: {e}")

    def validate_data(self, data):
        errors = []
        if 'serviceid' in data:
            service = ServiceRecord()
            service_data = service.read_by_pk(data['serviceid'])
            if not service_data:
                errors.append(f"ServiceRecord with ID {data['serviceid']} does not exist.")
        if 'mechanicid' in data:
            mechanic = Mechanic()
            mechanic_data = mechanic.read_by_pk(data['mechanicid'])
            if not mechanic_data:
                errors.append(f"Mechanic with ID {data['mechanicid']} does not exist.")
        return len(errors) == 0, errors

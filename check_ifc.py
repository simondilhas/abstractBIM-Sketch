def validate_ifc_file(file_path: str) -> bool:
    try:
        with open(file_path, 'r') as f:
            header = f.readline()
            if 'ISO-10303-21' not in header:
                print(f"Invalid IFC header: {header}")
                return False
                
            schema_line = None
            for line in f:
                if 'FILE_SCHEMA' in line:
                    schema_line = line
                    break
                    
            if not schema_line:
                print("No schema definition found")
                return False
                
            print(f"Schema line: {schema_line}")
            return True
            
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

if __name__ == "__main__":
    file_path = "Mustermodell V2.ifc"
    if validate_ifc_file(file_path):
        print("File appears valid, proceeding with conversion...")
    else:
        print("File validation failed")
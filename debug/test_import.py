import sys
import inspect

try:
    import chuk_protocol_server
    # Check ws_server_plain.py
    import chuk_protocol_server.servers.ws_server_plain as ws_plain
    print("\nClasses in ws_server_plain.py:")
    for name, obj in inspect.getmembers(ws_plain):
        if inspect.isclass(obj) and obj.__module__ == ws_plain.__name__:
            print(f"  - {name}")
    
    # Check ws_telnet_server.py
    import chuk_protocol_server.servers.ws_telnet_server as ws_telnet
    print("\nClasses in ws_telnet_server.py:")
    for name, obj in inspect.getmembers(ws_telnet):
        if inspect.isclass(obj) and obj.__module__ == ws_telnet.__name__:
            print(f"  - {name}")
            
    # Check the content of other files
    import chuk_protocol_server.servers.telnet_server as telnet_server
    print("\nClasses in telnet_server.py:")
    for name, obj in inspect.getmembers(telnet_server):
        if inspect.isclass(obj) and obj.__module__ == telnet_server.__name__:
            print(f"  - {name}")
            
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error examining modules: {e}")
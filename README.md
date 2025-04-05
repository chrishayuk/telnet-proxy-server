# Telnet Proxy Server

A flexible, multi-protocol telnet proxy server built on the chuk-protocol-server framework. This proxy enables connections to remote telnet servers through various protocols, including traditional telnet, TCP, WebSocket, and WebSocket-Telnet.

## Features

- **Multi-Protocol Support**: Connect via Telnet, TCP, WebSocket, and WebSocket-Telnet
- **Path-Based Routing**: Easy-to-remember URLs for accessing telnet services
- **Transparent Proxying**: Passes data between client and target without interference
- **Connection Tracking**: Real-time statistics on active connections
- **Configurable Default Target**: Fallback for connections without a specified target
- **SSL Support**: Secure WebSocket connections with SSL/TLS
- **Command-line Interface**: Quick setup with CLI options
- **YAML Configuration**: Detailed configuration for advanced deployments

## Installation

### Using pip

```bash
pip install telnet-proxy-server
```

### From source

1. Clone the repository:
   ```bash
   git clone https://github.com/chrishayuk/telnet-proxy-server.git
   cd telnet-proxy-server
   ```

2. Install dependencies:
   ```bash
   pip install -e .
   ```

## Quick Start

### Start the server

```bash
# Basic telnet proxy on port 8123
telnet-proxy-server --port 8123 --protocol telnet --default-target time.nist.gov:13

# WebSocket proxy on port 8125
telnet-proxy-server --port 8125 --protocol websocket --ws-path /ws
```

### Connect to services

```bash
# Connect to the default target (time.nist.gov:13)
telnet localhost 8123

# Connect to a specific server
telnet localhost 8123
# Then type: PROXY:CONNECT bbs.example.com:23
```

## Client Examples

### Traditional Telnet Clients

#### Using netcat
```bash
nc localhost 8123
```

#### Using the telnet command
```bash
telnet localhost 8123
```

#### Using PuTTY (Windows)
1. Open PuTTY
2. Set Host Name to `localhost`
3. Set Port to `8123`
4. Connection type: `Telnet`
5. Click "Open"

### WebSocket Clients

#### Browser-based WebSocket Console
```javascript
// In your browser's developer console
const ws = new WebSocket('ws://localhost:8125/ws/telehack.com/23');
ws.onmessage = function(event) {
  console.log(event.data);
};
ws.onopen = function() {
  console.log('Connection opened');
};
ws.send('help\r\n'); // Send command to the target
```

#### Using wscat (Command-line WebSocket client)
```bash
# Install wscat
npm install -g wscat

# Connect to the proxy with a specific target
wscat -c ws://localhost:8125/ws/telehack.com/23

# Connect to a predefined path
wscat -c ws://localhost:8125/time
```

## Configuration Options

### Command Line Arguments

```bash
telnet-proxy-server --help
```

Available options:

- `--host`: Server host (default: 0.0.0.0)
- `--port`: Server port (default: 8123)
- `--protocol`: Server protocol (choices: telnet, tcp, websocket, ws_telnet, default: telnet)
- `--default-target`: Default telnet target in the format host:port
- `--ws-path`: WebSocket path (default: /ws)
- `--no-allow-any-path`: Disallow connections on any WebSocket path (force fixed ws-path)
- `--use-ssl`: Use SSL for WebSocket connections
- `--ssl-cert`: Path to SSL certificate for WebSocket server
- `--ssl-key`: Path to SSL key for WebSocket server
- `--allow-origins`: Allowed origins for WebSocket connections (default: all)
- `--path-mapping`: Add a path mapping in the format path=host:port (can be specified multiple times)
- `--max-connections`: Maximum number of connections (default: 100)
- `--connection-timeout`: Connection timeout in seconds (default: 300)
- `--log-level`: Logging level (choices: DEBUG, INFO, WARNING, ERROR, default: INFO)

### YAML Configuration

Create a `config.yaml` file:

```yaml
servers:
  # Telnet protocol proxy server
  telnet_proxy:
    host: "0.0.0.0"
    port: 8123
    transport: "telnet"
    handler_class: "telnet_proxy_server.proxy_handler:TelnetProxyHandler"
    max_connections: 100
    connection_timeout: 300
    default_target: "time.nist.gov:13"  # Optional default target
    
  # WebSocket protocol proxy server
  websocket_proxy:
    host: "0.0.0.0"
    port: 8125
    transport: "websocket"
    ws_path: "/ws"
    handler_class: "telnet_proxy_server.proxy_handler:TelnetProxyHandler"
    use_ssl: false
    ssl_cert: ""
    ssl_key: ""
    allow_origins:
      - "*"
    ping_interval: 30
    ping_timeout: 10
    max_connections: 100
    connection_timeout: 300
    default_target: "telehack.com:23"
    # Path mappings for specific servers
    path_mappings:
      "/time": "time.nist.gov:13"
      "/starwars": "towel.blinkenlights.nl:23"
      "/telehack": "telehack.com:23"
```

Start with the configuration:

```bash
telnet-proxy-server --config config.yaml
```

## Docker Support

You can run the telnet proxy server in Docker:

```dockerfile
FROM python:3.11-alpine

WORKDIR /app

COPY . .
RUN pip install -e .

EXPOSE 8123 8125

CMD ["telnet-proxy-server", "--host", "0.0.0.0", "--port", "8123", "--protocol", "telnet", \
     "--default-target", "time.nist.gov:13", "--log-level", "INFO"]
```

Build and run:

```bash
docker build -t telnet-proxy-server .
docker run -p 8123:8123 -p 8125:8125 telnet-proxy-server
```

## Special Proxy Commands

While connected to the telnet proxy, you can use these special commands:

- `PROXY:QUIT` - Disconnect from the proxy server
- `PROXY:INFO` - Display connection information and statistics
- `PROXY:CONNECT host:port` - Connect to a different server without disconnecting
- `PROXY:STATS` - Show active connections and statistics

## Interesting Telnet Servers to Try

- `telehack.com:23` - Telehack BBS, a simulation of the early internet
- `towel.blinkenlights.nl:23` - ASCII Star Wars
- `time.nist.gov:13` - National Institute of Standards and Technology time server
- `mtrek.com:1701` - Multi-Player Star Trek game
- `mud.bat.org:23` - The Batcave MUD
- `borderlands.netsvcs.com:23` - Borderlands BBS, an active bulletin board system

## Path-Based Routing

The WebSocket mode supports path-based routing for easy connections:

```
ws://localhost:8125/ws/example.com/23
```

With path mappings, you can create friendly aliases:

```
ws://localhost:8125/starwars  # Connects to towel.blinkenlights.nl:23
```

## Security Considerations

- Do not expose the proxy to the public internet without proper authentication.
- Consider using SSL/TLS for WebSocket connections.
- Restrict allowed origins for WebSocket connections.
- Use a reverse proxy like Nginx for additional security layers.

## Troubleshooting

### Connection issues

1. Check that the proxy server is running: `telnet localhost 8123`
2. Verify target connectivity: `telnet time.nist.gov 13`
3. Check logs with increased verbosity: `telnet-proxy-server --log-level DEBUG`
4. Verify WebSocket path is correct: paths are case-sensitive

### Common errors

- **Connection refused**: The proxy server is not running or the port is blocked
- **Connection timeout**: The target server is unreachable or firewalled
- **Path not found**: For WebSocket connections, check the ws-path parameter
- **WebSocket handshake failed**: Check WebSocket protocol and allowed origins

## Advanced Usage

### SSL Configuration

For secure WebSocket connections:

```bash
telnet-proxy-server --protocol websocket --use-ssl --ssl-cert /path/to/cert.pem --ssl-key /path/to/key.pem
```

### Multiple Server Types

Run multiple server types simultaneously using a YAML configuration:

```yaml
servers:
  telnet_proxy:
    host: "0.0.0.0"
    port: 8123
    transport: "telnet"
    ...
  
  websocket_proxy:
    host: "0.0.0.0"
    port: 8125
    transport: "websocket"
    ...
```

### Custom Path Mappings

Create intuitive shortcuts to frequently used telnet servers:

```bash
telnet-proxy-server --protocol websocket --path-mapping /chat=irc.example.org:6667 --path-mapping /bbs=bbs.example.com:23
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

This telnet proxy server is built on top of the chuk-protocol-server framework.
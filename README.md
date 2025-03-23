# Telnet Proxy
A WebSocket to Telnet proxy server that allows web clients to connect to Telnet servers.

## Features

- WebSocket server that proxies connections to Telnet servers
- Support for multiple concurrent connections
- Dynamic target specification via query parameters
- Default target configuration via command-line options
- Graceful shutdown handling
- Detailed logging
- Compatibility with different versions of the WebSockets library

## Installation

### Prerequisites

- Python 3.7 or higher
- `websockets` library

### Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/telnet-proxy.git
   cd telnet-proxy
   ```

2. Install dependencies:
   ```bash
   pip install websockets
   ```

3. Make the main script executable (optional):
   ```bash
   chmod +x main.py
   ```

## Usage

### Starting the Server

Run the proxy server with default settings:

```bash
python -m telnet_proxy
```

Or directly:

```bash
./main.py
```

### Command-Line Options

- `--ws-host`: WebSocket server host (default: `0.0.0.0`)
- `--ws-port`: WebSocket server port (default: `8123`)
- `--default-target`: Default Telnet target in the format `host:port` (optional)

Example:

```bash
python -m telnet_proxy --ws-port 9000 --default-target example.com:23
```

### Connecting to the Server

Connect to the WebSocket server from a web client with a target specified:

```javascript
// Connect to a specific telnet server
const ws = new WebSocket('ws://localhost:8123?target=example.com:23');

// If default target is configured, you can connect without specifying a target
const ws = new WebSocket('ws://localhost:8123');

// Send data to the telnet server
ws.send('Some telnet command');

// Receive data from the telnet server
ws.onmessage = function(event) {
    console.log('Received:', event.data);
};
```

## Project Structure

The project follows a modular design with clear separation of concerns:

```
telnet_proxy/
├── __init__.py             # Package initialization
├── main.py                 # Entry point, argument parsing
├── server.py               # WebSocket server setup and main loop
├── client_handler.py       # Client connection handling logic
├── telnet_connection.py    # Telnet connection management
├── utils.py                # Utility functions
├── logger.py               # Logging configuration
└── banner.py               # ASCII art banner
```

### Module Responsibilities

- **main.py**: Parses command-line arguments and starts the server
- **server.py**: Sets up the WebSocket server and manages shutdown signals
- **client_handler.py**: Handles WebSocket client connections and requests
- **telnet_connection.py**: Manages connections to telnet servers
- **utils.py**: Contains helper functions and shared state
- **logger.py**: Configures logging for the application
- **banner.py**: Provides the ASCII art banner

## Technical Details

### State Tracking

The application tracks the following state information:

- Connected clients (ID-based tracking)
- Active telnet targets with connection counts

### Message Flow

1. Client connects to WebSocket server
2. Client request is parsed to extract the target
3. Connection is established to the target telnet server
4. Messages are bidirectionally forwarded between WebSocket and telnet
5. Resources are cleaned up on disconnection

## Error Handling

The application handles various error conditions:

- Invalid or missing target specification
- Connection failures to telnet servers
- Timeouts during connection or reading
- WebSocket disconnections
- Unexpected exceptions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
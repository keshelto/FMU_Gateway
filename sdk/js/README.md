# FMU Gateway JS SDK

## Installation
```bash
npm install ./sdk/js  # From local
# Or npm install fmu-gateway-sdk-js after publish
```

## Usage (Node.js)
```javascript
const { FMUGatewayClient } = require('fmu-gateway-sdk-js');

const client = new FMUGatewayClient('https://your-app.fly.dev');

async function example() {
  // Upload (Node.js)
  const meta = await client.uploadFmu('/path/to/model.fmu');
  const fmuId = meta.id;

  // Variables
  const vars = await client.getVariables(fmuId);

  // Simulate
  const req = {
    fmu_id: fmuId,
    stop_time: 1.0,
    step: 0.001,
    kpis: ['y_rms']
  };
  const result = await client.simulate(req);

  // Library
  const library = await client.getLibrary('Bouncing');
}

example();
```

For browser, adjust upload with File.

For API keys, pass apiKey to constructor.

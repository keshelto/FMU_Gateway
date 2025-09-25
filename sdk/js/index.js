const axios = require('axios');
const fs = require('fs');
const FormData = require('form-data');

class FMUGatewayClient {
  constructor(baseUrl, apiKey = null) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.client = axios.create({
      baseURL: this.baseUrl,
      headers: {}
    });
    if (apiKey) {
      this.client.defaults.headers.common['Authorization'] = `Bearer ${apiKey}`;
    }
  }

  async uploadFmu(filePath) {
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    const response = await this.client.post('/fmus', formData, {
      headers: {
        ...formData.getHeaders()
      }
    });
    return response.data;
  }

  async getVariables(fmuId) {
    const response = await this.client.get(`/fmus/${fmuId}/variables`);
    return response.data;
  }

  async simulate(req) {
    const response = await this.client.post('/simulate', req);
    return response.data;
  }

  async getLibrary(query = null) {
    const params = query ? { query } : {};
    const response = await this.client.get('/library', { params });
    return response.data;
  }
}

module.exports = { FMUGatewayClient };

import requests
from datetime import datetime

class WazuhAPI:
    def __init__(self, url, user, password, verify_ssl=False):
        self.url = url.rstrip('/'); self.auth = (user, password); self.verify = verify_ssl
        self.token = None; self.token_expires = None
    def _get_token(self):
        if self.token and self.token_expires and self.token_expires > datetime.utcnow(): return self.token
        try:
            res = requests.post(f"{self.url}/security/user/authenticate", auth=self.auth, verify=self.verify); res.raise_for_status()
            data = res.json(); self.token = data['data']['token']; self.token_expires = datetime.utcnow() + 800; return self.token
        except Exception as e: raise ConnectionError(f"Ошибка авторизации Wazuh: {str(e)}")
    def get_agents_page(self, limit=500, offset=0):
        token = self._get_token(); headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": limit, "offset": offset, "sort": "-lastKeepAlive"}
        res = requests.get(f"{self.url}/agents", headers=headers, params=params, verify=self.verify, timeout=15); res.raise_for_status(); return res.json()
    def fetch_all_agents(self):
        all_agents = []; offset = 0
        while True:
            try:
                data = self.get_agents_page(limit=500, offset=offset)
                agents = data.get('data', {}).get('affected_items', []); all_agents.extend(agents)
                if len(agents) < 500: break
                offset += 500
            except Exception as e: raise Exception(f"Ошибка получения агентов: {str(e)}")
        return all_agents

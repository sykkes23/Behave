import json
from app import app
client = app.test_client()
app.config['PROPAGATE_EXCEPTIONS'] = True
try:
    res = client.post('/api/test_ai/start', json={
        "baseline_endpoint": "",
        "candidate_endpoint": "",
        "provider": "http",
        "size": "QUICK"
    })
    print(res.status_code)
    print(res.data)
except Exception as e:
    import traceback
    traceback.print_exc()

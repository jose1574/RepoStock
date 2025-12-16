from app import app
import sqlite3

print('---URL RULES---')
for r in app.url_map.iter_rules():
    print(r)

# Use test client to POST create profile
c = app.test_client()
r = c.post('/systems/profile/create', data={'description': 'ui-test-profile'})
print('\nPOST /systems/profile/create status:', r.status_code)

conn = sqlite3.connect('repostock.db')
rows = conn.execute("SELECT id, description FROM profile WHERE description = ?", ('ui-test-profile',)).fetchall()
print('DB rows for ui-test-profile:', rows)
conn.close()

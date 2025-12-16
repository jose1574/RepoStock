from app import app
import sqlite3

print('---TEST POST WITH AUTHENTICATED SESSION---')
with app.test_client() as c:
    # set session user
    with c.session_transaction() as sess:
        sess['user'] = {'id': 1, 'description': 'tester'}
    r = c.post('/systems/profile/create', data={'description': 'ui-test-profile-auth'}, follow_redirects=True)
    print('status', r.status_code)
    conn = sqlite3.connect('repostock.db')
    rows = conn.execute("SELECT id, description FROM profile WHERE description = ?", ('ui-test-profile-auth',)).fetchall()
    print('DB rows for ui-test-profile-auth:', rows)
    conn.close()

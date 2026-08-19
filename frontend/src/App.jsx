import { useState, useEffect } from 'react';
import './index.css';

// Use the environment variable if set (like in Vercel), otherwise use the Render backend URL
const API_BASE = import.meta.env.VITE_API_URL || 'https://voice-agent-8sv8.onrender.com/api';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('orders');
  const [needsSetup, setNeedsSetup] = useState(false);
  const [checkingSetup, setCheckingSetup] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/auth/has-admin`)
      .then(res => res.json())
      .then(data => {
        setNeedsSetup(!data.has_admin);
        setCheckingSetup(false);
      })
      .catch(err => {
        console.error(err);
        setCheckingSetup(false);
      });
  }, []);

  if (checkingSetup) {
    return <div style={{display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center'}}>Loading...</div>;
  }

  if (needsSetup) {
    return <Setup onSetupComplete={() => setNeedsSetup(false)} onLogin={setToken} />;
  }

  if (!token) {
    return <Login onLogin={setToken} />;
  }

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div className="brand">Voice<span>Agent</span></div>
        <div 
          className={`nav-link ${activeTab === 'orders' ? 'active' : ''}`}
          onClick={() => setActiveTab('orders')}
        >
          Orders
        </div>
        <div 
          className={`nav-link ${activeTab === 'menu' ? 'active' : ''}`}
          onClick={() => setActiveTab('menu')}
        >
          Menu
        </div>
        <div style={{marginTop: 'auto'}}>
          <div className="nav-link" onClick={() => {
            localStorage.removeItem('token');
            setToken(null);
          }}>
            Logout
          </div>
        </div>
      </div>
      
      <div className="main-content">
        <header style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <h2>{activeTab === 'orders' ? 'Live Orders' : 'Menu Management'}</h2>
          <CallMeButton token={token} />
        </header>

        {activeTab === 'orders' && <Orders token={token} />}
        {activeTab === 'menu' && <Menu token={token} />}
      </div>
    </div>
  );
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!res.ok) throw new Error('Invalid credentials');
      
      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Welcome Back</h1>
        {error && <p style={{color: 'var(--danger)', marginBottom: '1rem'}}>{error}</p>}
        <form onSubmit={handleLogin}>
          <div className="input-group">
            <label>Username</label>
            <input value={username} onChange={e => setUsername(e.target.value)} />
          </div>
          <div className="input-group">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <button type="submit">Access Dashboard</button>
        </form>
      </div>
    </div>
  );
}

function Setup({ onSetupComplete, onLogin }) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');

  const handleSetup = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/auth/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          email,
          password,
          full_name: fullName
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Setup failed');
      
      localStorage.setItem('token', data.access_token);
      onLogin(data.access_token);
      onSetupComplete();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Initial Setup</h1>
        <p style={{marginBottom: '1rem', color: 'var(--text-muted)'}}>Create the first admin account</p>
        {error && <p style={{color: 'var(--danger)', marginBottom: '1rem'}}>{error}</p>}
        <form onSubmit={handleSetup}>
          <div className="input-group">
            <label>Username</label>
            <input required value={username} onChange={e => setUsername(e.target.value)} />
          </div>
          <div className="input-group">
            <label>Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="input-group">
            <label>Full Name</label>
            <input value={fullName} onChange={e => setFullName(e.target.value)} />
          </div>
          <div className="input-group">
            <label>Password</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} />
          </div>
          <button type="submit">Create Admin & Login</button>
        </form>
      </div>
    </div>
  );
}

function Orders({ token }) {
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/orders`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(async r => {
        if (!r.ok) {
          if (r.status === 401) {
             localStorage.removeItem('token');
             window.location.reload();
          }
          throw new Error('Failed to fetch');
        }
        return r.json();
      })
      .then(data => {
        if (Array.isArray(data)) setOrders(data);
        else setOrders([]);
      })
      .catch(console.error);
  }, [token]);

  return (
    <div className="card">
      <table>
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Customer Phone</th>
            <th>Total</th>
            <th>Status</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {orders.map(o => (
            <tr key={o.id}>
              <td>...{o.id.slice(-6)}</td>
              <td>{o.customer_phone}</td>
              <td>${o.total_amount.toFixed(2)}</td>
              <td><span className={`badge ${o.status}`}>{o.status}</span></td>
              <td>{new Date(o.created_at).toLocaleTimeString()}</td>
            </tr>
          ))}
          {orders.length === 0 && (
            <tr><td colSpan="5">No orders yet. Start calling your Twilio number!</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Menu({ token }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE}/menu/items`)
      .then(async r => {
        if (!r.ok) throw new Error('Failed to fetch');
        return r.json();
      })
      .then(data => {
        if (Array.isArray(data)) setItems(data);
        else setItems([]);
      })
      .catch(console.error);
  }, []);

  return (
    <div className="grid">
      {items.map(item => (
        <div className="menu-item" key={item.id}>
          <h3>{item.name}</h3>
          <p style={{color: 'var(--text-muted)', fontSize: '0.875rem', margin: '0.5rem 0'}}>
            {item.description}
          </p>
          <div className="price">${item.price.toFixed(2)}</div>
        </div>
      ))}
      {items.length === 0 && (
        <div className="menu-item">
          <h3>No Menu Items</h3>
          <p>Add some menu items via the API to see them here.</p>
        </div>
      )}
    </div>
  );
}

function CallMeButton({ token }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const triggerCall = async () => {
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`${API_BASE}/calls/trigger-outbound`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to call');
      setMessage('Phone is ringing! 📞');
      setTimeout(() => setMessage(''), 5000);
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{display: 'flex', alignItems: 'center', gap: '1rem'}}>
      {message && <span style={{fontSize: '0.875rem', color: message.startsWith('Error') ? 'var(--danger)' : 'var(--success)'}}>{message}</span>}
      <button 
        onClick={triggerCall} 
        disabled={loading}
        style={{width: 'auto', padding: '0.75rem 1.5rem', background: '#00e676', color: '#000'}}
      >
        {loading ? 'Calling...' : 'Call My Phone 📞'}
      </button>
    </div>
  );
}

export default App;

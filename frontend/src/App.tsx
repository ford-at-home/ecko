import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Record from './pages/Record';
import EchoList from './pages/EchoList';
import Playback from './pages/Playback';
import Health from './pages/Health';
import { EchoProvider } from './contexts/EchoContext';
import { AuthProvider } from './contexts/AuthContext';

function App() {
  return (
    <AuthProvider>
      <EchoProvider>
        <Router>
          <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Record />} />
                <Route path="echoes" element={<EchoList />} />
                <Route path="playback/:echoId" element={<Playback />} />
              </Route>
            </Routes>
          </div>
        </Router>
      </EchoProvider>
    </AuthProvider>
  );
}

export default App;
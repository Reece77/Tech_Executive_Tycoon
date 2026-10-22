import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { GameLayout } from './screens/GameLayout';
import { MainMenu } from './screens/MainMenu';
import { OverviewScreen } from './screens/OverviewScreen';
import { PlaceholderScreen } from './screens/PlaceholderScreen';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/game/:saveId" element={<GameLayout />}>
          {/* Inbox becomes home in M1b; until then Overview is the landing screen. */}
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewScreen />} />
          <Route path=":section" element={<PlaceholderScreen />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

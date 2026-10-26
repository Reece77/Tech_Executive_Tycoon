import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { GameLayout } from './screens/GameLayout';
import { InboxScreen } from './screens/InboxScreen';
import { MainMenu } from './screens/MainMenu';
import { NewGameScreen } from './screens/NewGameScreen';
import { OrgScreen } from './screens/OrgScreen';
import { OverviewScreen } from './screens/OverviewScreen';
import { PeopleScreen } from './screens/PeopleScreen';
import { PersonScreen } from './screens/PersonScreen';
import { PlaceholderScreen } from './screens/PlaceholderScreen';
import { RecruitmentScreen } from './screens/RecruitmentScreen';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/new" element={<NewGameScreen />} />
        <Route path="/game/:saveId" element={<GameLayout />}>
          <Route index element={<Navigate to="inbox" replace />} />
          <Route path="inbox" element={<InboxScreen />} />
          <Route path="overview" element={<OverviewScreen />} />
          <Route path="people" element={<PeopleScreen />} />
          <Route path="people/:personId" element={<PersonScreen />} />
          <Route path="recruitment" element={<RecruitmentScreen />} />
          <Route path="org" element={<OrgScreen />} />
          <Route path=":section" element={<PlaceholderScreen />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

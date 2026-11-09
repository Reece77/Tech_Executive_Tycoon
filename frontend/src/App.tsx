import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { CompetitorsScreen } from './screens/CompetitorsScreen';
import { FinanceScreen } from './screens/FinanceScreen';
import { GameLayout } from './screens/GameLayout';
import { GameOverScreen } from './screens/GameOverScreen';
import { HistoryScreen } from './screens/HistoryScreen';
import { EventRedirect, InboxScreen } from './screens/InboxScreen';
import { ExplorationScreen } from './screens/ExplorationScreen';
import { HardwareScreen } from './screens/HardwareScreen';
import { InfrastructureScreen } from './screens/InfrastructureScreen';
import { MainMenu } from './screens/MainMenu';
import { MarketScreen } from './screens/MarketScreen';
import { NewGameScreen } from './screens/NewGameScreen';
import { OfficesScreen } from './screens/OfficesScreen';
import { ResearchScreen } from './screens/ResearchScreen';
import { OrgScreen } from './screens/OrgScreen';
import { OverviewScreen } from './screens/OverviewScreen';
import { PeopleScreen } from './screens/PeopleScreen';
import { PersonScreen } from './screens/PersonScreen';
import { PlaceholderScreen } from './screens/PlaceholderScreen';
import { ProductScreen } from './screens/ProductScreen';
import { ProductsScreen } from './screens/ProductsScreen';
import { RecruitmentScreen } from './screens/RecruitmentScreen';
import { RankingsScreen } from './screens/RankingsScreen';
import { RivalScreen } from './screens/RivalScreen';
import { SavesScreen } from './screens/SavesScreen';
import { SettingsScreen } from './screens/SettingsScreen';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/new" element={<NewGameScreen />} />
        <Route path="/saves" element={<MainMenu />} />
        <Route path="/game/:saveId/over" element={<GameOverScreen />} />
        <Route path="/game/:saveId" element={<GameLayout />}>
          <Route index element={<Navigate to="inbox" replace />} />
          {/* One route, so opening a message (M7c deep link) keeps the folder filter. */}
          <Route path="inbox/:itemId?" element={<InboxScreen />} />
          <Route path="events/:eventId" element={<EventRedirect />} />
          <Route path="overview" element={<OverviewScreen />} />
          <Route path="people" element={<PeopleScreen />} />
          <Route path="people/:personId" element={<PersonScreen />} />
          <Route path="recruitment" element={<RecruitmentScreen />} />
          <Route path="org" element={<OrgScreen />} />
          <Route path="org/offices" element={<OfficesScreen />} />
          <Route path="products" element={<ProductsScreen />} />
          <Route path="products/research" element={<ResearchScreen />} />
          <Route path="products/markets" element={<MarketScreen />} />
          <Route path="products/infrastructure" element={<InfrastructureScreen />} />
          <Route path="products/hardware" element={<HardwareScreen />} />
          <Route path="products/exploration" element={<ExplorationScreen />} />
          <Route path="products/markets/:category" element={<MarketScreen />} />
          <Route path="products/:productId" element={<ProductScreen />} />
          <Route path="finance" element={<FinanceScreen />} />
          <Route path="finance/:tab" element={<FinanceScreen />} />
          <Route path="competitors" element={<CompetitorsScreen />} />
          <Route path="competitors/rankings" element={<RankingsScreen />} />
          <Route path="competitors/:rivalId" element={<RivalScreen />} />
          <Route path="settings" element={<SettingsScreen />} />
          <Route path="saves" element={<SavesScreen />} />
          <Route path="history" element={<HistoryScreen />} />
          <Route path="history/:tab" element={<HistoryScreen />} />
          <Route path=":section" element={<PlaceholderScreen />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

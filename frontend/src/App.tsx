import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { FinanceScreen } from './screens/FinanceScreen';
import { GameLayout } from './screens/GameLayout';
import { GameOverScreen } from './screens/GameOverScreen';
import { InboxScreen } from './screens/InboxScreen';
import { MainMenu } from './screens/MainMenu';
import { MarketScreen } from './screens/MarketScreen';
import { NewGameScreen } from './screens/NewGameScreen';
import { OrgScreen } from './screens/OrgScreen';
import { OverviewScreen } from './screens/OverviewScreen';
import { PeopleScreen } from './screens/PeopleScreen';
import { PersonScreen } from './screens/PersonScreen';
import { PlaceholderScreen } from './screens/PlaceholderScreen';
import { ProductScreen } from './screens/ProductScreen';
import { ProductsScreen } from './screens/ProductsScreen';
import { RecruitmentScreen } from './screens/RecruitmentScreen';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/new" element={<NewGameScreen />} />
        <Route path="/game/:saveId/over" element={<GameOverScreen />} />
        <Route path="/game/:saveId" element={<GameLayout />}>
          <Route index element={<Navigate to="inbox" replace />} />
          <Route path="inbox" element={<InboxScreen />} />
          <Route path="overview" element={<OverviewScreen />} />
          <Route path="people" element={<PeopleScreen />} />
          <Route path="people/:personId" element={<PersonScreen />} />
          <Route path="recruitment" element={<RecruitmentScreen />} />
          <Route path="org" element={<OrgScreen />} />
          <Route path="products" element={<ProductsScreen />} />
          <Route path="products/markets" element={<MarketScreen />} />
          <Route path="products/markets/:category" element={<MarketScreen />} />
          <Route path="products/:productId" element={<ProductScreen />} />
          <Route path="finance" element={<FinanceScreen />} />
          <Route path="finance/:tab" element={<FinanceScreen />} />
          <Route path=":section" element={<PlaceholderScreen />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

import { BrowserRouter, Navigate, Route, Routes } from 'react-router';
import { DesktopPrompts } from './components/DesktopPrompts';
import { AchievementsScreen } from './screens/AchievementsScreen';
import { ScenariosScreen } from './screens/ScenariosScreen';
import { AutomationScreen } from './screens/AutomationScreen';
import { DataEditorScreen } from './screens/DataEditorScreen';
import { CompetitorsScreen } from './screens/CompetitorsScreen';
import { FamilyScreen } from './screens/FamilyScreen';
import { FinanceScreen } from './screens/FinanceScreen';
import { GameLayout } from './screens/GameLayout';
import { GameOverScreen } from './screens/GameOverScreen';
import { GuideScreen } from './screens/GuideScreen';
import { HistoryScreen } from './screens/HistoryScreen';
import { EventRedirect, InboxScreen } from './screens/InboxScreen';
import { ExplorationScreen } from './screens/ExplorationScreen';
import { RefineriesScreen } from './screens/RefineriesScreen';
import { FabsScreen } from './screens/FabsScreen';
import { MinesScreen } from './screens/MinesScreen';
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
import { PressScreen } from './screens/PressScreen';
import { ProductScreen } from './screens/ProductScreen';
import { ProductsScreen } from './screens/ProductsScreen';
import { RecruitmentScreen } from './screens/RecruitmentScreen';
import { RankingsScreen } from './screens/RankingsScreen';
import { RivalScreen } from './screens/RivalScreen';
import { SavesScreen } from './screens/SavesScreen';
import { SettingsScreen } from './screens/SettingsScreen';
import { WorldNewsScreen } from './screens/WorldNewsScreen';
import { EquipmentScreen } from './screens/EquipmentScreen';
import { PlatformsScreen } from './screens/PlatformsScreen';
import { PowerPlantScreen, PowerScreen } from './screens/PowerScreen';
import { VehicleCarScreen, VehiclesScreen } from './screens/VehiclesScreen';
import { MedicalScreen } from './screens/MedicalScreen';
import { PharmaPlantScreen, PharmaProgrammeScreen, PharmaScreen } from './screens/PharmaScreen';
import { RoboticsScreen } from './screens/RoboticsScreen';
import { MobilityScreen } from './screens/MobilityScreen';
import { SpaceScreen } from './screens/SpaceScreen';
import { GamesScreen, SocialScreen, StreamingScreen, StudioScreen } from './screens/MediaScreens';
import { TelecomScreen } from './screens/TelecomScreen';
import { GovernmentScreen } from './screens/GovernmentScreen';
import { RegulationScreen } from './screens/RegulationScreen';
import { WorldScreen } from './screens/WorldScreen';

export default function App() {
  return (
    <BrowserRouter>
      <DesktopPrompts />
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/new" element={<NewGameScreen />} />
        <Route path="/achievements" element={<AchievementsScreen />} />
        <Route path="/scenarios" element={<ScenariosScreen />} />
        <Route path="/mods" element={<DataEditorScreen />} />
        <Route path="/saves" element={<MainMenu />} />
        <Route path="/game/:saveId/over" element={<GameOverScreen />} />
        <Route path="/game/:saveId" element={<GameLayout />}>
          <Route index element={<Navigate to="inbox" replace />} />
          {/* One route, so opening a message (M7c deep link) keeps the folder filter. */}
          <Route path="inbox/:itemId?" element={<InboxScreen />} />
          <Route path="events/:eventId" element={<EventRedirect />} />
          <Route path="overview" element={<OverviewScreen />} />
          <Route path="press" element={<PressScreen />} />
          <Route path="people" element={<PeopleScreen />} />
          <Route path="people/family" element={<FamilyScreen />} />
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
          <Route path="products/refineries" element={<RefineriesScreen />} />
          <Route path="products/fabs" element={<FabsScreen />} />
          <Route path="products/power" element={<PowerScreen />} />
          <Route path="products/power/plants/:facilityId" element={<PowerPlantScreen />} />
          <Route path="products/vehicles" element={<VehiclesScreen />} />
          <Route path="products/vehicles/cars/:productId" element={<VehicleCarScreen />} />
          <Route path="products/robotics" element={<RoboticsScreen />} />
          <Route path="products/mobility" element={<MobilityScreen />} />
          <Route path="products/space" element={<SpaceScreen />} />
          <Route path="products/telecom" element={<TelecomScreen />} />
          <Route path="products/studio" element={<StudioScreen />} />
          <Route path="products/streaming" element={<StreamingScreen />} />
          <Route path="products/games" element={<GamesScreen />} />
          <Route path="products/social" element={<SocialScreen />} />
          <Route path="products/government" element={<GovernmentScreen />} />
          <Route path="products/equipment" element={<EquipmentScreen />} />
          <Route path="products/medical" element={<MedicalScreen />} />
          <Route path="products/pharma" element={<PharmaScreen />} />
          <Route
            path="products/pharma/programme/:programmeId"
            element={<PharmaProgrammeScreen />}
          />
          <Route path="products/pharma/plant/:plantId" element={<PharmaPlantScreen />} />
          <Route path="products/mines" element={<MinesScreen />} />
          <Route path="products/markets/:category" element={<MarketScreen />} />
          <Route path="products/:productId" element={<ProductScreen />} />
          <Route path="finance" element={<FinanceScreen />} />
          <Route path="finance/:tab" element={<FinanceScreen />} />
          <Route path="competitors" element={<CompetitorsScreen />} />
          <Route path="competitors/rankings" element={<RankingsScreen />} />
          <Route path="competitors/world" element={<WorldScreen />} />
          <Route path="competitors/world-news" element={<WorldNewsScreen />} />
          <Route path="competitors/platforms" element={<PlatformsScreen />} />
          <Route path="competitors/regulation" element={<RegulationScreen />} />
          <Route path="competitors/:rivalId" element={<RivalScreen />} />
          <Route path="automation" element={<AutomationScreen />} />
          <Route path="settings" element={<SettingsScreen />} />
          <Route path="saves" element={<SavesScreen />} />
          <Route path="history" element={<HistoryScreen />} />
          <Route path="history/:tab" element={<HistoryScreen />} />
          <Route path="guide/:guideKey?" element={<GuideScreen />} />
          <Route path=":section" element={<PlaceholderScreen />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

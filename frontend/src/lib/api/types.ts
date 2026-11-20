import type { components } from "./schema";

type Schemas = components["schemas"];

export type Me = Schemas["MeOut"];
export type User = Schemas["UserOut"];
export type Team = Schemas["TeamOut"];
export type TeamDetail = Schemas["TeamDetailOut"];
export type Scorecard = Schemas["ScorecardOut"];
export type MeasurableRow = Schemas["MeasurableRowOut"];
export type Cell = Schemas["CellOut"];
export type Issue = Schemas["IssueOut"];
export type Todos = Schemas["TodosOut"];
export type Todo = Schemas["TodoOut"];
export type Rocks = Schemas["RocksOut"];
export type Rock = Schemas["RockOut"];
export type MeetingState = Schemas["MeetingStateOut"];
export type MeetingSummary = Schemas["MeetingSummaryOut"];
export type MeetingListItem = Schemas["MeetingListItemOut"];
export type MeasurableStatus = Cell["status"];

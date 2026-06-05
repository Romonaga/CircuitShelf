import { lazy } from "react";

export const AccountView = lazy(() => import("../AccountView").then((module) => ({ default: module.AccountView })));
export const AIUsageView = lazy(() => import("../AIUsageView").then((module) => ({ default: module.AIUsageView })));
export const BenchView = lazy(() => import("../BenchView").then((module) => ({ default: module.BenchView })));
export const DocumentsView = lazy(() => import("../DocumentsView").then((module) => ({ default: module.DocumentsView })));
export const EntitySettingsView = lazy(() => import("../EntitySettingsView").then((module) => ({ default: module.EntitySettingsView })));
export const InventoryView = lazy(() => import("../InventoryView").then((module) => ({ default: module.InventoryView })));
export const PerformanceView = lazy(() => import("../PerformanceView").then((module) => ({ default: module.PerformanceView })));
export const ProjectFinderView = lazy(() => import("../ProjectFinderView").then((module) => ({ default: module.ProjectFinderView })));
export const ReviewView = lazy(() => import("../ReviewView").then((module) => ({ default: module.ReviewView })));
export const RuntimeCatalogView = lazy(() => import("../RuntimeCatalogView").then((module) => ({ default: module.RuntimeCatalogView })));
export const SettingsView = lazy(() => import("../SettingsView").then((module) => ({ default: module.SettingsView })));
export const StatusView = lazy(() => import("../StatusView").then((module) => ({ default: module.StatusView })));
export const TraceView = lazy(() => import("../TraceView").then((module) => ({ default: module.TraceView })));
export const WorkView = lazy(() => import("../WorkView").then((module) => ({ default: module.WorkView })));

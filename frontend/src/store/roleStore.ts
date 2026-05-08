import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Role = 'analyst' | 'supervisor' | 'manager';

export interface RoleSpec {
  id: Role;
  label: string;
  username: string;
  // What this role can DO (capability flags consumed by the UI)
  canDismiss: boolean;
  canInvestigate: boolean;
  canEscalate: boolean;
  canBulkAction: boolean;
  canRegenerateNarrative: boolean;
  canViewAuditLog: boolean;
  canViewDepartmentRollup: boolean;
  canApproveEscalations: boolean;
  shortDescription: string;
}

export const ROLES: Record<Role, RoleSpec> = {
  analyst: {
    id: 'analyst',
    label: 'Analyst',
    username: 'analyst@hawkeye.local',
    canDismiss: true,
    canInvestigate: true,
    canEscalate: false,
    canBulkAction: false,
    canRegenerateNarrative: false,
    canViewAuditLog: false,
    canViewDepartmentRollup: false,
    canApproveEscalations: false,
    shortDescription: 'Tier-1 fraud analyst — read alerts, triage individually, view graph + employee detail.',
  },
  supervisor: {
    id: 'supervisor',
    label: 'Supervisor',
    username: 'supervisor@hawkeye.local',
    canDismiss: true,
    canInvestigate: true,
    canEscalate: true,
    canBulkAction: true,
    canRegenerateNarrative: true,
    canViewAuditLog: true,
    canViewDepartmentRollup: false,
    canApproveEscalations: true,
    shortDescription: 'Tier-2 supervisor — escalate, regenerate narrative, audit-log access, approve queue.',
  },
  manager: {
    id: 'manager',
    label: 'Branch Manager',
    username: 'manager@hawkeye.local',
    canDismiss: true,
    canInvestigate: true,
    canEscalate: true,
    canBulkAction: true,
    canRegenerateNarrative: true,
    canViewAuditLog: true,
    canViewDepartmentRollup: true,
    canApproveEscalations: true,
    shortDescription: 'Branch Manager — full supervision powers + department rollup + bulk actions + audit feed.',
  },
};

interface RoleStore {
  role: Role;
  setRole: (r: Role) => void;
}

export const useRoleStore = create<RoleStore>()(
  persist(
    (set) => ({
      role: 'manager', // default to manager so the demo lands on the richest view
      setRole: (r) => set({ role: r }),
    }),
    { name: 'hawkeye:role' },
  ),
);

export const useRole = () => {
  const role = useRoleStore((s) => s.role);
  return ROLES[role];
};

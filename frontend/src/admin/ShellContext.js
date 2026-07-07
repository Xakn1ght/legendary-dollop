import { createContext, useContext } from 'react';

// Shared shell state: navigation + live receipts/support badges + receipts data.
export const ShellContext = createContext(null);
export function useShell() { return useContext(ShellContext); }

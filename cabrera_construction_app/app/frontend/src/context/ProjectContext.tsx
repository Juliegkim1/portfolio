import { useQuery } from "@tanstack/react-query";
import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Project } from "../api/types";

interface ProjectContextValue {
  projects: Project[];
  selectedProjectId: number | null;
  setSelectedProjectId: (id: number) => void;
  selectedProject: Project | undefined;
  isLoading: boolean;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

const STORAGE_KEY = "cabrera.selectedProjectId";

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { data: projects = [], isLoading } = useQuery({ queryKey: ["projects"], queryFn: api.projects.list });
  const [selectedProjectId, setSelectedProjectIdState] = useState<number | null>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : null;
  });

  useEffect(() => {
    if (selectedProjectId === null && projects.length > 0) {
      setSelectedProjectIdState(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  const setSelectedProjectId = (id: number) => {
    setSelectedProjectIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  };

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <ProjectContext.Provider value={{ projects, selectedProjectId, setSelectedProjectId, selectedProject, isLoading }}>
      {children}
    </ProjectContext.Provider>
  );
}

export function useProjectContext() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProjectContext must be used within ProjectProvider");
  return ctx;
}

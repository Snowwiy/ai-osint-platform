import { useParams } from "react-router-dom";

export function useInvestigationId(): string {
  const { investigationId } = useParams();
  if (!investigationId) {
    throw new Error("Missing investigation id");
  }
  return investigationId;
}


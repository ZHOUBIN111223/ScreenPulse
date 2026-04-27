// Legacy route kept only to redirect older links into the research-group workspace.
import { redirect } from "next/navigation";

export default function TeamsPage() {
  redirect("/research-groups");
}

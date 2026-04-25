// Legacy route kept only to redirect older links into the team workspace.
import { redirect } from "next/navigation";

export default function AdminPage() {
  redirect("/teams");
}

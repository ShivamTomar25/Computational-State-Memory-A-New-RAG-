import { useState } from "react";
import { KeyRound, ShieldAlert, Trash2 } from "lucide-react";
import {
  InfoRow,
  PageHero,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  SelectField,
  StatusBadge,
  TableShell,
  TextField,
} from "../platform_shared/PlatformShell";
import { loginHistory, sessions as sessionFixtures } from "../platform_shared/platformService";

export function SecuritySessionsPage() {
  const [sessions, setSessions] = useState(sessionFixtures);
  const [mfaState, setMfaState] = useState("Not Configured");
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [passwordError, setPasswordError] = useState("");
  const [passwordSaved, setPasswordSaved] = useState(false);

  function updatePassword(field, value) {
    setPasswordForm((current) => ({ ...current, [field]: value }));
    setPasswordError("");
    setPasswordSaved(false);
  }

  function changePassword(event) {
    event.preventDefault();

    if (!passwordForm.currentPassword || !passwordForm.newPassword) {
      setPasswordError("Current password and new password are required.");
      return;
    }

    if (passwordForm.newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters.");
      return;
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }

    setPasswordSaved(true);
    setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
  }

  function revokeSession(id) {
    setSessions((current) => current.filter((session) => session.id !== id || session.current));
  }

  function revokeOthers() {
    setSessions((current) => current.filter((session) => session.current));
  }

  return (
    <PlatformShell sectionLabel="Security">
      <PageHero
        eyebrow="Account security"
        title="Security and Session Management"
        description="Manage password updates, active sessions, login history, multi-factor authentication status, and security alerts."
      />

      <section className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <form onSubmit={changePassword} className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-2">
            <KeyRound className="h-5 w-5 text-blue-700" aria-hidden="true" />
            <h2 className="text-base font-semibold text-slate-950">Password</h2>
          </div>
          <div className="mt-5 grid gap-5 md:grid-cols-3">
            <TextField label="Current password" type="password" value={passwordForm.currentPassword} onChange={(value) => updatePassword("currentPassword", value)} />
            <TextField label="New password" type="password" value={passwordForm.newPassword} onChange={(value) => updatePassword("newPassword", value)} />
            <TextField label="Confirm password" type="password" value={passwordForm.confirmPassword} onChange={(value) => updatePassword("confirmPassword", value)} />
          </div>
          {passwordError ? <p className="mt-4 text-sm font-medium text-red-700">{passwordError}</p> : null}
          {passwordSaved ? <p className="mt-4 text-sm font-medium text-green-700">Password change submitted.</p> : null}
          <div className="mt-5">
            <PrimaryButton type="submit">Change Password</PrimaryButton>
          </div>
        </form>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-950">Multi-factor authentication</h2>
          <div className="mt-4">
            <SelectField label="MFA state" value={mfaState} onChange={setMfaState} options={["Not Configured", "Enabled", "Recovery Codes Available"]} />
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            MFA setup UI is prepared. Custom cryptography is not implemented in
            the frontend.
          </p>
        </section>
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-base font-semibold text-slate-950">Active sessions</h2>
          <SecondaryButton onClick={revokeOthers}>Sign Out All Other Sessions</SecondaryButton>
        </div>
        <div className="mt-4">
          <TableShell caption="Active sessions" columns={["Device", "Browser", "Location", "Login Time", "Last Active", "Current", "Actions"]}>
            {sessions.map((session) => (
              <tr key={session.id}>
                <td className="px-5 py-4 text-sm text-slate-600">{session.device}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{session.browser}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{session.location}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{session.loginTime}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{session.lastActive}</td>
                <td className="px-5 py-4">{session.current ? <StatusBadge label="Active" /> : <span className="text-sm text-slate-500">No</span>}</td>
                <td className="px-5 py-4">
                  <SecondaryButton disabled={session.current} onClick={() => revokeSession(session.id)}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Sign Out Session
                  </SecondaryButton>
                </td>
              </tr>
            ))}
          </TableShell>
        </div>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-950">Login history</h2>
          <div className="mt-4">
            <TableShell caption="Login history" columns={["Event", "Timestamp", "Device", "Region", "Status"]}>
              {loginHistory.map((event) => (
                <tr key={event.id}>
                  <td className="px-5 py-4 text-sm text-slate-600">{event.event}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{event.timestamp}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{event.device}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{event.region}</td>
                  <td className="px-5 py-4"><StatusBadge label={event.status} /></td>
                </tr>
              ))}
            </TableShell>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-700" aria-hidden="true" />
            <h2 className="text-base font-semibold text-slate-950">Security alerts</h2>
          </div>
          <dl className="mt-4 grid gap-3 text-sm">
            <InfoRow label="Unusual login" value="No active alert" />
            <InfoRow label="Password changed" value={passwordSaved ? "Just now" : "No recent change"} />
            <InfoRow label="Session revoked" value="No recent revocation" />
            <InfoRow label="Repeated failed login" value="1 failed attempt in last 7 days" />
          </dl>
        </section>
      </section>
    </PlatformShell>
  );
}

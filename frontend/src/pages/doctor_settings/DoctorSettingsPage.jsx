import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import {
  getAuthToken,
  getCurrentDoctor,
  updateCurrentDoctor,
} from "../login_page/authApi";
import {
  PageHero,
  PlatformShell,
  PrimaryButton,
  SelectField,
  TextField,
  ToggleRow,
} from "../platform_shared/PlatformShell";

const initialSettings = {
  fullName: "Doctor",
  email: "",
  specialization: "",
  medicalLicenseNumber: "",
  organization: "",
  displayName: "Doctor",
  patientListView: "Table",
  defaultMemorySystem: "Dense RAG",
  comparisonSystems: "Dense RAG, Hybrid RAG, CSM",
  timelineDensity: "Comfortable",
  citationDisplay: "Expanded",
  technicalDetails: true,
  dateFormat: "DD MMMM YYYY",
  timeFormat: "12-hour",
  language: "English",
  theme: "System",
  documentCompletion: true,
  processingFailure: true,
  evidenceConflict: true,
  reviewRequest: true,
  experimentCompletion: true,
  securityAlert: true,
  showExecutionMetadata: true,
  showEstimatedCost: true,
  showModelVersion: true,
  defaultExportFormat: "JSON",
  defaultEvaluationScale: "5-point",
  reducedMotion: false,
  textSize: "Default",
  highContrast: false,
};

export function DoctorSettingsPage() {
  const [settings, setSettings] = useState(initialSettings);
  const [saved, setSaved] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const isSignedIn = Boolean(getAuthToken());

  useEffect(() => {
    let isActive = true;

    if (!getAuthToken()) {
      return () => {
        isActive = false;
      };
    }

    getCurrentDoctor()
      .then((doctor) => {
        if (isActive) {
          applyDoctorProfile(doctor);
        }
      })
      .catch((error) => {
        if (isActive) {
          setProfileError(
            error instanceof Error
              ? error.message
              : "Unable to load doctor profile.",
          );
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  function applyDoctorProfile(doctor) {
    setSettings((current) => ({
      ...current,
      fullName: doctor.full_name ?? "",
      email: doctor.email ?? "",
      specialization: doctor.specialization ?? "",
      medicalLicenseNumber: doctor.medical_license_number ?? "",
      organization: doctor.organization_name ?? "",
      displayName: doctor.full_name ?? current.displayName,
    }));
  }

  function update(field, value) {
    setSettings((current) => ({ ...current, [field]: value }));
    setSaved(false);
  }

  async function saveSettings(event) {
    event.preventDefault();
    setSaved(false);
    setProfileError(null);

    if (!isSignedIn) {
      setSaved(true);
      return;
    }

    try {
      setIsSaving(true);

      const doctor = await updateCurrentDoctor({
        full_name: settings.fullName,
        specialization: settings.specialization || null,
        medical_license_number: settings.medicalLicenseNumber || null,
        organization_name: settings.organization || null,
      });

      applyDoctorProfile(doctor);
      setSaved(true);
    } catch (error) {
      setProfileError(
        error instanceof Error ? error.message : "Unable to save profile.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <PlatformShell sectionLabel="Doctor settings">
      <PageHero
        eyebrow="Account preferences"
        title="Doctor Settings"
        description="Manage profile details, notification preferences, research defaults, and accessibility options."
        actions={
          <PrimaryButton type="submit" onClick={saveSettings} disabled={isSaving}>
            <Save className="h-4 w-4" aria-hidden="true" />
            {isSaving ? "Saving..." : "Save Settings"}
          </PrimaryButton>
        }
      />

      {!isSignedIn ? (
        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm font-medium text-amber-800">
          Sign in to load and save the doctor profile from the backend.
        </div>
      ) : null}

      {profileError ? (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm font-medium text-red-700">
          {profileError}
        </div>
      ) : null}

      {saved ? (
        <div className="mt-6 rounded-xl border border-green-200 bg-green-50 px-5 py-4 text-sm font-medium text-green-800">
          Settings saved.
        </div>
      ) : null}

      <form onSubmit={saveSettings} className="mt-6 space-y-6">
        <SettingsSection title="Profile">
          <div className="grid gap-5 md:grid-cols-2">
            <TextField label="Full name" value={settings.fullName} onChange={(value) => update("fullName", value)} />
            <ReadOnlyField label="Email" value={settings.email || "Sign in required"} />
            <TextField label="Specialization" value={settings.specialization} onChange={(value) => update("specialization", value)} />
            <TextField label="Medical license number" value={settings.medicalLicenseNumber} onChange={(value) => update("medicalLicenseNumber", value)} />
            <TextField label="Organization" value={settings.organization} onChange={(value) => update("organization", value)} />
            <TextField label="Preferred display name" value={settings.displayName} onChange={(value) => update("displayName", value)} />
          </div>
        </SettingsSection>

        <SettingsSection title="Preferences">
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            <SelectField label="Default patient-list view" value={settings.patientListView} onChange={(value) => update("patientListView", value)} options={["Table", "Cards", "Compact"]} />
            <SelectField label="Default memory system" value={settings.defaultMemorySystem} onChange={(value) => update("defaultMemorySystem", value)} options={["Dense RAG", "Hybrid RAG", "GraphRAG", "CSM"]} />
            <TextField label="Default comparison systems" value={settings.comparisonSystems} onChange={(value) => update("comparisonSystems", value)} />
            <SelectField label="Default timeline density" value={settings.timelineDensity} onChange={(value) => update("timelineDensity", value)} options={["Comfortable", "Compact"]} />
            <SelectField label="Citation display" value={settings.citationDisplay} onChange={(value) => update("citationDisplay", value)} options={["Expanded", "Compact", "Drawer"]} />
            <SelectField label="Technical details visibility" value={settings.technicalDetails ? "Visible" : "Hidden"} onChange={(value) => update("technicalDetails", value === "Visible")} options={["Visible", "Hidden"]} />
            <SelectField label="Date format" value={settings.dateFormat} onChange={(value) => update("dateFormat", value)} options={["DD MMMM YYYY", "YYYY-MM-DD", "MM/DD/YYYY"]} />
            <SelectField label="Time format" value={settings.timeFormat} onChange={(value) => update("timeFormat", value)} options={["12-hour", "24-hour"]} />
            <SelectField label="Language" value={settings.language} onChange={(value) => update("language", value)} options={["English"]} />
            <SelectField label="Theme" value={settings.theme} onChange={(value) => update("theme", value)} options={["System", "Light"]} />
          </div>
        </SettingsSection>

        <SettingsSection title="Notifications">
          <div className="grid gap-4 md:grid-cols-2">
            <ToggleRow label="Document completion" checked={settings.documentCompletion} onChange={(value) => update("documentCompletion", value)} />
            <ToggleRow label="Processing failure" checked={settings.processingFailure} onChange={(value) => update("processingFailure", value)} />
            <ToggleRow label="Evidence conflict" checked={settings.evidenceConflict} onChange={(value) => update("evidenceConflict", value)} />
            <ToggleRow label="Review request" checked={settings.reviewRequest} onChange={(value) => update("reviewRequest", value)} />
            <ToggleRow label="Experiment completion" checked={settings.experimentCompletion} onChange={(value) => update("experimentCompletion", value)} />
            <ToggleRow label="Security alert" checked={settings.securityAlert} onChange={(value) => update("securityAlert", value)} />
          </div>
        </SettingsSection>

        <SettingsSection title="Research Preferences">
          <div className="grid gap-4 md:grid-cols-2">
            <ToggleRow label="Show execution metadata" checked={settings.showExecutionMetadata} onChange={(value) => update("showExecutionMetadata", value)} />
            <ToggleRow label="Show estimated cost" checked={settings.showEstimatedCost} onChange={(value) => update("showEstimatedCost", value)} />
            <ToggleRow label="Show model version" checked={settings.showModelVersion} onChange={(value) => update("showModelVersion", value)} />
            <SelectField label="Default export format" value={settings.defaultExportFormat} onChange={(value) => update("defaultExportFormat", value)} options={["JSON", "CSV", "PDF"]} />
            <SelectField label="Default evaluation scale" value={settings.defaultEvaluationScale} onChange={(value) => update("defaultEvaluationScale", value)} options={["5-point", "Pass-fail", "Rubric"]} />
          </div>
        </SettingsSection>

        <SettingsSection title="Accessibility">
          <div className="grid gap-4 md:grid-cols-2">
            <ToggleRow label="Reduced motion" checked={settings.reducedMotion} onChange={(value) => update("reducedMotion", value)} />
            <ToggleRow label="High-contrast preference" checked={settings.highContrast} onChange={(value) => update("highContrast", value)} />
            <SelectField label="Text size" value={settings.textSize} onChange={(value) => update("textSize", value)} options={["Default", "Large"]} />
            <SelectField label="Keyboard shortcut help" value="Enabled" onChange={() => {}} options={["Enabled"]} />
          </div>
        </SettingsSection>
      </form>
    </PlatformShell>
  );
}

function SettingsSection({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>
      <input
        type="text"
        value={value}
        readOnly
        className="h-11 w-full rounded-lg border border-slate-300 bg-slate-50 px-3.5 text-sm text-slate-600 outline-none"
      />
    </label>
  );
}

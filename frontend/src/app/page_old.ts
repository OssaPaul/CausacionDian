"use client";

import React, { useState, useEffect } from "react";
import {
  Zap,
  Lock,
  Mail,
  UserCheck,
  Cpu,
  Database,
  FileSpreadsheet,
  LogOut,
  RefreshCw,
  UploadCloud,
  Activity,
  Coins,
  FileOutput,
  Download,
  Trash2,
  Edit,
  XCircle,
  Plus,
  Building,
  CreditCard,
  Building2,
  Calculator,
  Server,
  CheckCircle2,
  Receipt,
  AlertTriangle,
  Eye
} from "lucide-react";

interface CompanyItem {
  id: string;
  name: string;
  nit: string;
  organization_id?: string;
  is_active?: boolean;
}

interface OrganizationItem {
  id: string;
  name: string;
  nit: string;
  is_active?: boolean;
  created_at?: string;
}
 
export interface SubscriptionPlanItem {
  id: string;
  code: string;
  name: string;
  credits_allocated: number;
  monthly_fee: number;
  additional_credit_fee: number;
  is_active: boolean;
  created_at?: string;
}

interface SubscriptionItem {
  id: string;
  organization_id?: string;
  organizations?: { name: string; nit?: string };
  plan_name: string;
  credits_allocated: number;
  credits_used?: number;
  credits_remaining?: number;
  monthly_fee?: number;
  billing_cycle?: string;
  start_date?: string;
  end_date?: string;
  is_active?: boolean;
}

interface UserProfile {
  id: string;
  full_name: string;
  email: string;
  role: "SUPER_ADMIN" | "COMPANY_ADMIN" | "COMPANY_OPERATOR" | "COMPANY_EXPORTER";
  organization_id?: string;
  is_active: boolean;
}

interface AccountingParameter {
  id: string;
  organization_id: string;
  concept_code: string;
  concept_name: string;
  account_puc: string;
  account_name: string;
  nature: "D" | "C";
}

interface EmailIntegration {
  id: string;
  organization_id: string;
  direction: "RECIBIDA" | "EMITIDA";
  imap_server: string;
  imap_port: number;
  email_account: string;
  folder_name: string;
  scan_frequency_minutes: number;
  is_active: boolean;
}

interface InvoiceItemRow {
  id: string;
  direction: string;
  full_number: string;
  issue_date: string;
  issuer_nit: string;
  issuer_name: string;
  line_extension_amount: number;
  payable_amount: number;
  status: string;
  cufe?: string; // <-- Añadido
}

interface JournalEntryPreview {
  invoice_id: string;
  full_number: string;
  grouping_mode: string;
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
  lines: {
    account_puc: string;
    account_name: string;
    third_party_nit: string;
    third_party_name: string;
    debit: number;
    credit: number;
    description: string;
  }[];
}

interface BillingOrgRow {
  organization_id: string;
  organization_name: string;
  organization_nit: string;
  subscription_id: string | null;
  plan_name: string;
  is_active: boolean;
  credits_allocated: number;
  credits_used: number;
  credits_remaining: number;
  invoices_parsed: number;
  invoices_caused: number;
  invoices_total: number;
  monthly_fee: number;
  billing_cycle: string;
  end_date: string | null;
  billing_status: string;
}

export default function SaaSApplication() {
  const API_BASE = "http://127.0.0.1:8000";

  // --- ESTADO DE AUTENTICACIÓN ---
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [loginEmail, setLoginEmail] = useState("possar1961@gmail.com");
  const [loginPassword, setLoginPassword] = useState("PoR1961$");
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<string>("");
  const [organizationsList, setOrganizationsList] = useState<OrganizationItem[]>([]);
  const [companiesList, setCompaniesList] = useState<CompanyItem[]>([]);
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);

  // --- NAVEGACIÓN PRINCIPAL & PESTAÑAS (TABS) ---
  const [activeTab, setActiveTab] = useState<"operacion" | "mantenimiento" | "exportacion" | "facturacion">("operacion");
  const [maintenanceSubTab, setMaintenanceSubTab] = useState<
    "organizations" | "users" | "companies" | "accounting" | "emails" | "subscriptions"
  >("organizations");

const [maintenanceSubTab, setMaintenanceSubTab] = useState<
    "organizations" | "users" | "companies" | "accounting" | "emails" | "subscriptions" | "plans" | "unspsc"
  >("organizations");

  // --- ESTADO DE OPERACIÓN, FACTURAS & SUSCRIPCIÓN ACTIVA ---
  const [isSyncingEmails, setIsSyncingEmails] = useState(false);
  // --- ESTADO VISOR DE FACTURA DIAN / DETALLES ---
  const [invoiceDetailModal, setInvoiceDetailModal] = useState<{
    invoice: any;
    items: any[];
    taxes: any[];
  } | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [orgSubscription, setOrgSubscription] = useState<SubscriptionItem | null>(null);
  const [invoicesList, setInvoicesList] = useState<InvoiceItemRow[]>([]);
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<string[]>([]);
  const [groupingMode, setGroupingMode] = useState<"CONSOLIDATED" | "DETAILED">("CONSOLIDATED");
  const [isCausing, setIsCausing] = useState(false);
  const [journalPreview, setJournalPreview] = useState<JournalEntryPreview | null>(null);
  const [manualXmlFile, setManualXmlFile] = useState<File | null>(null);
  const [isUploadingManual, setIsUploadingManual] = useState(false);

// --- ESTADOS PARA PLANES DE SUSCRIPCIÓN ---
  const [subscriptionPlansList, setSubscriptionPlansList] = useState<SubscriptionPlanItem[]>([]);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [planFormData, setPlanFormData] = useState({
    code: "",
    name: "",
    credits_allocated: 1000,
    monthly_fee: 150000,
    additional_credit_fee: 150,
    is_active: true
  });
  
  // --- ESTADO FACTURACIÓN SAAS (SUPER_ADMIN) ---
  const [billingKpis, setBillingKpis] = useState({
    total_organizations: 0,
    active_subscriptions: 0,
    total_mrr: 0,
    total_invoices_caused: 0
  });
  const [billingRows, setBillingRows] = useState<BillingOrgRow[]>([]);

  // --- ESTADOS DE FORMULARIOS (CREAR Y EDITAR) ---
  const [showOrgForm, setShowOrgForm] = useState(false);
  const [editingOrgId, setEditingOrgId] = useState<string | null>(null);
  const [orgFormData, setOrgFormData] = useState({ name: "", nit: "" });
  const [isSavingOrg, setIsSavingOrg] = useState(false);

  const [showUserForm, setShowUserForm] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [usersList, setUsersList] = useState<UserProfile[]>([]);
  const [userFormData, setUserFormData] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "COMPANY_ADMIN" as UserProfile["role"]
  });

  const [showCompanyForm, setShowCompanyForm] = useState(false);
  const [editingCompanyId, setEditingCompanyId] = useState<string | null>(null);
  const [companyFormData, setCompanyFormData] = useState({ name: "", nit: "" });
  const [isSavingCompany, setIsSavingCompany] = useState(false);

  const [showSubForm, setShowSubForm] = useState(false);
  const [editingSubId, setEditingSubId] = useState<string | null>(null);
  const [subscriptionsList, setSubscriptionsList] = useState<SubscriptionItem[]>([]);
  const [subFormData, setSubFormData] = useState({
    organization_id: "",
    plan_name: "ENTERPRISE",
    credits_allocated: 1000,
    credits_used: 0,
    monthly_fee: 150000,
    billing_cycle: "MONTHLY",
    start_date: "",
    end_date: "",
    is_active: true
  });

  const [showParamForm, setShowParamForm] = useState(false);
  const [editingParamId, setEditingParamId] = useState<string | null>(null);
  const [accountingParamsList, setAccountingParamsList] = useState<AccountingParameter[]>([]);
  const [paramFormData, setParamFormData] = useState({
    concept_code: "",
    concept_name: "",
    account_puc: "",
    account_name: "",
    nature: "D" as "D" | "C"
  });
  const [paramSearchFilter, setParamSearchFilter] = useState("");

  // --- CORREOS IMAP (company_email_integrations) ---
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [editingEmailId, setEditingEmailId] = useState<string | null>(null);
  const [emailIntegrationsList, setEmailIntegrationsList] = useState<EmailIntegration[]>([]);
  const [emailFormData, setEmailFormData] = useState({
    direction: "RECIBIDA" as "RECIBIDA" | "EMITIDA",
    imap_server: "imap.gmail.com",
    imap_port: 993,
    email_account: "",
    email_password: "",
    folder_name: "INBOX",
    scan_frequency_minutes: 15,
    is_active: true
  });

  // --- EXPORTACIÓN ERP ---
  const [selectedErp, setSelectedErp] = useState("siigo");

  // --- CARGA PÚBLICA DE ORGANIZACIONES PARA LOGIN ---
  const loadPublicOrganizations = async () => {
    try {
      const resOrg = await fetch(`${API_BASE}/auth/organizations`);
      const dataOrg = await resOrg.json();
      if (dataOrg.organizations) {
        setOrganizationsList(dataOrg.organizations);
      }
    } catch (e) {
      console.error("Error cargando organizaciones para login", e);
    }
  };

  // --- CARGA DE DATOS OPERATIVOS (SUSCRIPCIÓN ACTIVA + FACTURAS) ---
  const loadOperationalData = async (token: string) => {
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const resSub = await fetch(`${API_BASE}/subscription/current`, { headers });
      if (resSub.ok) {
        const dataSub = await resSub.json();
        setOrgSubscription(dataSub.has_subscription ? dataSub.subscription : null);
      }

      const resInv = await fetch(`${API_BASE}/invoices`, { headers });
      if (resInv.ok) {
        const dataInv = await resInv.json();
        setInvoicesList(dataInv.invoices || []);
      }
    } catch (err) {
      console.error("Error cargando datos operativos:", err);
    }
  };

  // --- CARGA DE TODAS LAS TABLAS DE MANTENIMIENTO Y FACTURACIÓN CON TOKEN ---
  const loadAllMaintenanceTables = async (token: string, role: string) => {
    const headers = { Authorization: `Bearer ${token}` };

    try {
      const resOrg = await fetch(`${API_BASE}/auth/organizations`);
      const dataOrg = await resOrg.json();
      if (dataOrg.organizations) setOrganizationsList(dataOrg.organizations);

      if (role === "SUPER_ADMIN" || role === "COMPANY_ADMIN") {
        const resUsers = await fetch(`${API_BASE}/auth/users`, { headers });
        if (resUsers.ok) {
          const dataUsers = await resUsers.json();
          setUsersList(dataUsers.data || dataUsers.users || []);
        }

        const resComp = await fetch(`${API_BASE}/companies`, { headers });
        if (resComp.ok) {
          const dataComp = await resComp.json();
          setCompaniesList(dataComp.data || dataComp.companies || []);
        }

        const resParams = await fetch(`${API_BASE}/accounting-parameters`, { headers });
        if (resParams.ok) {
          const dataParams = await resParams.json();
          setAccountingParamsList(dataParams.data || dataParams.parameters || []);
        }

        const resEmails = await fetch(`${API_BASE}/email-integrations`, { headers });
        if (resEmails.ok) {
          const dataEmails = await resEmails.json();
          setEmailIntegrationsList(dataEmails.data || dataEmails.integrations || []);
        }
      }

      if (role === "SUPER_ADMIN") {
        const resSubs = await fetch(`${API_BASE}/subscriptions`, { headers });
        if (resSubs.ok) {
          const dataSubs = await resSubs.json();
          setSubscriptionsList(dataSubs.data || dataSubs.subscriptions || []);
        }
		
		const resPlans = await fetch(`${API_BASE}/subscription-plans`, { headers });
        if (resPlans.ok) {
          const dataPlans = await resPlans.json();
          // Si el backend devuelve un arreglo directo o un objeto con .data / .plans / .subscription_plans
          const plansArray = Array.isArray(dataPlans) 
            ? dataPlans 
            : (dataPlans.data || dataPlans.plans || dataPlans.subscription_plans || []);
          setSubscriptionPlansList(plansArray);
        }
		
        const resBilling = await fetch(`${API_BASE}/billing/summary`, { headers });
        if (resBilling.ok) {
          const dataBilling = await resBilling.json();
          setBillingKpis(dataBilling.kpis || billingKpis);
          setBillingRows(dataBilling.organizations_billing || []);
        }
      }
    } catch (err) {
      console.error("Error sincronizando tablas maestras:", err);
    }
  };

  useEffect(() => {
    loadPublicOrganizations();

    const token = localStorage.getItem("access_token");
    const storedUser = localStorage.getItem("user_info");
    if (token && storedUser) {
      const parsedUser = JSON.parse(storedUser);
      setIsAuthenticated(true);
      setCurrentUser(parsedUser);
      if (parsedUser.role !== "SUPER_ADMIN") {
        setMaintenanceSubTab("users");
      }
      loadOperationalData(token);
      loadAllMaintenanceTables(token, parsedUser.role);
    }
  }, []);

  // --- LOGIN ---
  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    setIsLoggingIn(true);

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: loginEmail,
          password: loginPassword,
          selected_organization_id: selectedOrganizationId || null
        })
      });

      const data = await response.json();

      if (response.ok && data.access_token) {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("user_info", JSON.stringify(data.user));
        setCurrentUser(data.user);
        setIsAuthenticated(true);

        if (data.user.role !== "SUPER_ADMIN") {
          setMaintenanceSubTab("users");
        } else {
          setMaintenanceSubTab("organizations");
        }
        loadOperationalData(data.access_token);
        loadAllMaintenanceTables(data.access_token, data.user.role);
      } else {
        setLoginError(data.detail || "Credenciales inválidas o organización no seleccionada.");
      }
    } catch (err) {
      setLoginError("Error de conexión con el backend en FastAPI (127.0.0.1:8000).");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_info");
    setIsAuthenticated(false);
    setCurrentUser(null);
  };

  // --- OPERACIÓN: SINCRONIZAR CORREOS ---
  const handleManualEmailSync = async () => {
    setIsSyncingEmails(true);
    const token = localStorage.getItem("access_token") || "";

    try {
      const res = await fetch(`${API_BASE}/sync-emails`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || "Sincronización de correos ejecutada.");
        loadOperationalData(token);
      } else {
        alert("Bloqueo / Error: " + (data.detail || "Revise la suscripción o la consola"));
      }
    } catch (err) {
      alert("Error de conexión con el backend al sincronizar correos.");
    } finally {
      setIsSyncingEmails(false);
    }
  };

  const handleOpenInvoiceDetails = async (invoiceId: string) => {
    setIsLoadingDetails(true);
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/invoices/${invoiceId}/details`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        setInvoiceDetailModal(data);
      } else {
        alert("Error cargando detalles de la factura: " + (data.detail || "Desconocido"));
      }
    } catch (err) {
      alert("Error de conexión al consultar detalles.");
    } finally {
      setIsLoadingDetails(false);
    }
  };

  // --- OPERACIÓN: CARGA MANUAL XML ---
  const handleManualXmlUpload = async () => {
    if (!manualXmlFile) {
      alert("Seleccione primero un archivo .xml o .zip.");
      return;
    }
    const token = localStorage.getItem("access_token") || "";
    const orgId = currentUser?.organization_id;
    if (!orgId) return;

    setIsUploadingManual(true);
    try {
      const formData = new FormData();
      formData.append("organization_id", orgId);
      formData.append("direction", "RECIBIDA");
      formData.append("file", manualXmlFile);

      const res = await fetch(`${API_BASE}/upload-xml`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        alert(`¡Factura ${data.full_number} cargada exitosamente!`);
        setManualXmlFile(null);
        loadOperationalData(token);
      } else {
        alert("Bloqueo / Error: " + (data.detail || "No se pudo procesar el XML"));
      }
    } catch (err) {
      alert("Error de conexión subiendo el archivo XML.");
    } finally {
      setIsUploadingManual(false);
    }
  };

  // --- OPERACIÓN: CAUSACIÓN INDIVIDUAL Y MASIVA ---
  const handleCausarSingle = async (invoiceId: string, currentStatus: string) => {
    const token = localStorage.getItem("access_token") || "";

    // Si ya está causada, consultamos directamente el asiento desde journal_lines
    if (currentStatus === "CAUSADO") {
      try {
        const res = await fetch(`${API_BASE}/invoices/${invoiceId}/journal`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok) {
          setJournalPreview(data);
        } else {
          alert("Error cargando el asiento contable: " + (data.detail || "Desconocido"));
        }
      } catch (err) {
        alert("Error de conexión al consultar el asiento.");
      }
      return;
    }

    // Si está pendiente (PARSEADO), procedemos a causar
    setIsCausing(true);
    try {
      const res = await fetch(
        `${API_BASE}/causar-factura/${invoiceId}?grouping_mode=${groupingMode}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      const data = await res.json();
      if (res.ok) {
        setJournalPreview(data);
        loadOperationalData(token);
        if (currentUser?.role === "SUPER_ADMIN") {
          loadAllMaintenanceTables(token, "SUPER_ADMIN");
        }
      } else {
        alert("Bloqueo / Error al causar: " + (data.detail || "Verifique suscripción y PUC"));
      }
    } catch (err) {
      alert("Error de conexión al causar factura.");
    } finally {
      setIsCausing(false);
    }
  };
  const handleCausarBatch = async () => {
    if (selectedInvoiceIds.length === 0) {
      alert("Seleccione al menos una factura en estado PARSEADO.");
      return;
    }
    setIsCausing(true);
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/causar-masivo`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          invoice_ids: selectedInvoiceIds,
          grouping_mode: groupingMode
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(
          `Proceso masivo finalizado: ${data.caused_count} causadas, ${data.errors_count} con error.`
        );
        if (data.results && data.results.length > 0) {
          setJournalPreview(data.results[data.results.length - 1]);
        }
        setSelectedInvoiceIds([]);
        loadOperationalData(token);
        if (currentUser?.role === "SUPER_ADMIN") {
          loadAllMaintenanceTables(token, "SUPER_ADMIN");
        }
      } else {
        alert("Error en causación masiva: " + (data.detail || "Verifique datos"));
      }
    } catch (err) {
      alert("Error de conexión en causación masiva.");
    } finally {
      setIsCausing(false);
    }
  };

  const toggleSelectInvoice = (id: string) => {
    setSelectedInvoiceIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // ============================================================================
  // 1. CRUD ORGANIZACIONES (SOLO SUPER_ADMIN)
  // ============================================================================
  const handleSaveOrganization = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingOrg(true);
    const token = localStorage.getItem("access_token") || "";

    try {
      const url = editingOrgId
        ? `${API_BASE}/organizations/${editingOrgId}`
        : `${API_BASE}/organizations`;
      const method = editingOrgId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ name: orgFormData.name, nit: orgFormData.nit })
      });

      const data = await res.json();
      if (res.ok) {
        alert(editingOrgId ? "¡Organización actualizada!" : "¡Organización registrada exitosamente!");
        setShowOrgForm(false);
        setEditingOrgId(null);
        setOrgFormData({ name: "", nit: "" });
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        alert("Error: " + (data.detail || "No se pudo guardar la organización"));
      }
    } catch (err) {
      alert("Error conectando con FastAPI");
    } finally {
      setIsSavingOrg(false);
    }
  };

  const handleEditOrganization = (org: OrganizationItem) => {
    setEditingOrgId(org.id);
    setOrgFormData({ name: org.name, nit: org.nit });
    setShowOrgForm(true);
  };

  const handleDeleteOrganization = async (orgId: string, orgName: string) => {
    if (!confirm(`¿Seguro que deseas eliminar la organización "${orgName}"?`)) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/organizations/${orgId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Organización eliminada.");
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        const data = await res.json();
        alert("Error al eliminar: " + (data.detail || "Tiene registros asociados"));
      }
    } catch (err) {
      alert("Error de conexión con backend");
    }
  };

  // ============================================================================
  // 2. CRUD USUARIOS CON JERARQUÍA ESTRICTA
  // ============================================================================
  const handleSaveUser = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("access_token") || "";
    const activeOrgId = currentUser?.organization_id;

    if (!activeOrgId) {
      alert("Error relacional: No se detectó una Organización Activa en la sesión.");
      return;
    }

    try {
      const url = editingUserId
        ? `${API_BASE}/auth/users/${editingUserId}`
        : `${API_BASE}/auth/users`;
      const method = editingUserId ? "PUT" : "POST";

      const payloadUser = {
        full_name: userFormData.full_name,
        email: userFormData.email,
        password: userFormData.password,
        role: userFormData.role,
        organization_id: activeOrgId,
        is_active: true
      };

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payloadUser)
      });
      const result = await response.json();

      if (response.ok) {
        alert(editingUserId ? "¡Usuario actualizado!" : "¡Usuario registrado e hipervinculado a la Organización Activa!");
        setShowUserForm(false);
        setEditingUserId(null);
        setUserFormData({
          full_name: "",
          email: "",
          password: "",
          role: currentUser?.role === "SUPER_ADMIN" ? "COMPANY_ADMIN" : "COMPANY_OPERATOR"
        });
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        alert("Error: " + (result.detail || "Consulte permisos"));
      }
    } catch (err) {
      alert("Error conectando con el backend");
    }
  };

  const handleEditUser = (u: UserProfile) => {
    setEditingUserId(u.id);
    setUserFormData({
      full_name: u.full_name,
      email: u.email,
      password: "",
      role: u.role
    });
    setShowUserForm(true);
  };

  const handleDeleteUser = async (userId: string, fullName: string) => {
    if (!confirm(`¿Seguro que deseas eliminar al usuario "${fullName}"?`)) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/auth/users/${userId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Usuario eliminado.");
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        const data = await res.json();
        alert("Error al eliminar usuario: " + (data.detail || "Operación no permitida"));
      }
    } catch (err) {
      alert("Error de conexión con backend");
    }
  };

  // ============================================================================
  // 3. CRUD EXCEPCIONES NIT / COMPANIES (SUPER_ADMIN Y COMPANY_ADMIN)
  // ============================================================================
  const handleSaveCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingCompany(true);
    const token = localStorage.getItem("access_token") || "";

    try {
      const url = editingCompanyId
        ? `${API_BASE}/companies/${editingCompanyId}`
        : `${API_BASE}/companies`;
      const method = editingCompanyId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: companyFormData.name,
          nit: companyFormData.nit,
          organization_id: currentUser?.organization_id
        })
      });

      const data = await res.json();
      if (res.ok) {
        alert(editingCompanyId ? "¡Excepción NIT actualizada!" : "¡Excepción NIT registrada!");
        setShowCompanyForm(false);
        setEditingCompanyId(null);
        setCompanyFormData({ name: "", nit: "" });
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        alert("Error: " + (data.detail || "Permisos insuficientes"));
      }
    } catch (err) {
      alert("Error conectando con FastAPI");
    } finally {
      setIsSavingCompany(false);
    }
  };

  const handleEditCompany = (c: CompanyItem) => {
    setEditingCompanyId(c.id);
    setCompanyFormData({ name: c.name, nit: c.nit });
    setShowCompanyForm(true);
  };

  const handleDeleteCompany = async (companyId: string, name: string) => {
    if (!confirm(`¿Seguro que deseas eliminar la excepción NIT "${name}"?`)) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/companies/${companyId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Registro eliminado.");
        loadAllMaintenanceTables(token, currentUser?.role);
      }
    } catch (err) {
      alert("Error eliminando registro");
    }
  };

  // ============================================================================
  // 4. CRUD PARÁMETROS CONTABLES PUC / DIAN (SUPER_ADMIN Y COMPANY_ADMIN)
  // ============================================================================
  const handleSaveAccountingParam = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("access_token") || "";

    try {
      const url = editingParamId
        ? `${API_BASE}/accounting-parameters/${editingParamId}`
        : `${API_BASE}/accounting-parameters`;
      const method = editingParamId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          ...paramFormData,
          organization_id: currentUser?.organization_id
        })
      });

      const data = await res.json();
      if (res.ok) {
        alert(editingParamId ? "¡Parámetro contable actualizado!" : "¡Parámetro contable creado!");
        setShowParamForm(false);
        setEditingParamId(null);
        setParamFormData({
          concept_code: "",
          concept_name: "",
          account_puc: "",
          account_name: "",
          nature: "D"
        });
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        alert("Error: " + (data.detail || "Verifique datos del parámetro"));
      }
    } catch (err) {
      alert("Error conectando con FastAPI");
    }
  };

  const handleEditAccountingParam = (p: AccountingParameter) => {
    setEditingParamId(p.id);
    setParamFormData({
      concept_code: p.concept_code,
      concept_name: p.concept_name || "",
      account_puc: p.account_puc,
      account_name: p.account_name,
      nature: p.nature
    });
    setShowParamForm(true);
  };

  const handleDeleteAccountingParam = async (paramId: string, code: string) => {
    if (!confirm(`¿Seguro que deseas eliminar el parámetro contable "${code}"?`)) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/accounting-parameters/${paramId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Parámetro contable eliminado.");
        loadAllMaintenanceTables(token, currentUser?.role);
      }
    } catch (err) {
      alert("Error eliminando parámetro");
    }
  };

  // ============================================================================
  // 5. CRUD CORREOS IMAP (company_email_integrations - SUPER_ADMIN Y COMPANY_ADMIN)
  // ============================================================================
  const handleSaveEmailIntegration = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("access_token") || "";

    try {
      const url = editingEmailId
        ? `${API_BASE}/email-integrations/${editingEmailId}`
        : `${API_BASE}/email-integrations`;
      const method = editingEmailId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          ...emailFormData,
          organization_id: currentUser?.organization_id
        })
      });

      const data = await res.json();
      if (res.ok) {
        alert(editingEmailId ? "¡Cuenta IMAP actualizada!" : "¡Cuenta IMAP registrada exitosamente!");
        setShowEmailForm(false);
        setEditingEmailId(null);
        setEmailFormData({
          direction: "RECIBIDA",
          imap_server: "imap.gmail.com",
          imap_port: 993,
          email_account: "",
          email_password: "",
          folder_name: "INBOX",
          scan_frequency_minutes: 15,
          is_active: true
        });
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        alert("Error: " + (data.detail || "No se pudo guardar la integración IMAP"));
      }
    } catch (err) {
      alert("Error conectando con FastAPI");
    }
  };

  const handleEditEmailIntegration = (item: EmailIntegration) => {
    setEditingEmailId(item.id);
    setEmailFormData({
      direction: item.direction,
      imap_server: item.imap_server,
      imap_port: item.imap_port,
      email_account: item.email_account,
      email_password: "",
      folder_name: item.folder_name || "INBOX",
      scan_frequency_minutes: item.scan_frequency_minutes || 15,
      is_active: item.is_active
    });
    setShowEmailForm(true);
  };

  const handleDeleteEmailIntegration = async (id: string, email: string) => {
    if (!confirm(`¿Seguro que deseas eliminar la integración IMAP "${email}"?`)) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/email-integrations/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Integración IMAP eliminada.");
        loadAllMaintenanceTables(token, currentUser?.role);
      }
    } catch (err) {
      alert("Error eliminando integración IMAP");
    }
  };

  // ============================================================================
  // 6. CRUD SUSCRIPCIONES COMPLETO (SOLO SUPER_ADMIN)
  // ============================================================================
  const handleSaveSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("access_token") || "";

    try {
      const url = editingSubId
        ? `${API_BASE}/subscriptions/${editingSubId}`
        : `${API_BASE}/subscriptions`;
      const method = editingSubId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(subFormData)
      });
      if (res.ok) {
        alert(editingSubId ? "¡Suscripción actualizada!" : "¡Suscripción registrada exitosamente!");
        setShowSubForm(false);
        setEditingSubId(null);
        setSubFormData({
		organization_id: currentUser?.organization_id || "",
		plan_name: "ENTERPRISE",
		credits_allocated: 1000,
		credits_used: 0,
		monthly_fee: 150000,
		billing_cycle: "MONTHLY",
		start_date: new Date().toISOString().slice(0, 10),
		end_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
		is_active: true
	  });
        loadOperationalData(token);
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        const data = await res.json();
        alert("Error guardando suscripción: " + (data.detail || "Verifique datos"));
      }
    } catch (err) {
      alert("Error conectando con backend");
    }
  };

  const handleEditSubscription = (s: SubscriptionItem) => {
    setEditingSubId(s.id);
    setSubFormData({
      organization_id: s.organization_id || "",
      plan_name: s.plan_name,
      credits_allocated: s.credits_allocated,
      credits_used: s.credits_used || 0,
      monthly_fee: s.monthly_fee || 0,
      billing_cycle: s.billing_cycle || "MONTHLY",
      start_date: s.start_date || new Date().toISOString().slice(0, 10),
      end_date: s.end_date || new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
      is_active: s.is_active !== undefined ? s.is_active : true
    });
    setShowSubForm(true);
  };

  const handleDeleteSubscription = async (subId: string) => {
    if (!confirm("¿Seguro que deseas eliminar esta suscripción?")) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/subscriptions/${subId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Suscripción eliminada.");
        loadOperationalData(token);
        loadAllMaintenanceTables(token, currentUser?.role);
      }
    } catch (err) {
      alert("Error eliminando suscripción");
    }
  };

// ----------------------------------------------------
  // PEGA AQUÍ LAS NUEVAS FUNCIONES DE PLANES COMERCIALES:
  // ----------------------------------------------------
  const handleSaveSubscriptionPlan = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("access_token") || "";

    try {
      const url = editingPlanId ? `${API_BASE}/subscription-plans/${editingPlanId}` : `${API_BASE}/subscription-plans`;
      const method = editingPlanId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(planFormData)
      });
      const data = await res.json();
      if (res.ok) {
        alert(editingPlanId ? "¡Plan actualizado exitosamente!" : "¡Plan comercial creado exitosamente!");
        setShowPlanForm(false);
        setEditingPlanId(null);
        setPlanFormData({
          code: "",
          name: "",
          credits_allocated: 1000,
          monthly_fee: 150000,
          additional_credit_fee: 150,
          is_active: true
        });
        loadAllMaintenanceTables(token, currentUser?.role);
      } else {
        alert("Error guardando plan: " + (data.detail || "Verifique datos"));
      }
    } catch (err) {
      alert("Error conectando con backend");
    }
  };

  const handleEditSubscriptionPlan = (plan: any) => {
    setEditingPlanId(plan.id);
    setPlanFormData({
      code: plan.code,
      name: plan.name,
      credits_allocated: plan.credits_allocated,
      monthly_fee: plan.monthly_fee,
      additional_credit_fee: plan.additional_credit_fee,
      is_active: plan.is_active
    });
    setShowPlanForm(true);
  };

  const handleDeleteSubscriptionPlan = async (planId: string, planName: string) => {
    if (!confirm(`¿Seguro que deseas eliminar el plan "${planName}"?`)) return;
    const token = localStorage.getItem("access_token") || "";
    try {
      const res = await fetch(`${API_BASE}/subscription-plans/${planId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Plan eliminado.");
        loadAllMaintenanceTables(token, currentUser?.role);
      }
    } catch (err) {
      alert("Error eliminando plan");
    }
  };

  // ==================== VISTA LOGIN ====================
  if (!isAuthenticated) {
    const isSuperAdminEmail =
      loginEmail.toLowerCase().includes("possar") || loginEmail.toLowerCase().includes("admin");

    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4 font-sans">
        <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8 space-y-6">
          <div className="text-center space-y-2">
            <div className="inline-flex p-3 bg-indigo-600/20 text-indigo-400 rounded-2xl border border-indigo-500/30">
              <Zap className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Acceso al Portal SaaS</h1>
            <p className="text-xs text-slate-400">Causaciones Automáticas DIAN & Multi-Tenant Engine</p>
          </div>

          {loginError && (
            <div className="p-3.5 bg-rose-950/80 border border-rose-800/80 rounded-xl text-xs text-rose-300 flex items-center gap-2">
              <XCircle className="w-4 h-4 shrink-0" />
              <span>{loginError}</span>
            </div>
          )}

          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Correo Electrónico
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                  placeholder="usuario@empresa.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Contraseña
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex justify-between">
                <span>Organización Activa (Tenant)</span>
                {isSuperAdminEmail && (
                  <span className="text-indigo-400 font-mono text-[10px]">(SUPER_ADMIN)</span>
                )}
              </label>
              <div className="relative">
                <Building className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <select
                  value={selectedOrganizationId}
                  onChange={(e) => setSelectedOrganizationId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                >
                  <option value="">-- Seleccione Organización --</option>
                  {organizationsList.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name} (NIT: {o.nit})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoggingIn}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 rounded-xl text-sm shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {isLoggingIn ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Validar e Ingresar"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  // ==================== VISTA DASHBOARD PRINCIPAL ====================
  const isSuperAdmin = currentUser?.role === "SUPER_ADMIN";
  const isCompanyAdmin = currentUser?.role === "COMPANY_ADMIN";
  const canManageTenantTables = isSuperAdmin || isCompanyAdmin;

  const activeOrgName =
    organizationsList.find((o) => o.id === currentUser?.organization_id)?.name ||
    "ORGANIZACIÓN ACTIVA";

  const filteredParams = accountingParamsList.filter(
    (p) =>
      p.concept_code.toLowerCase().includes(paramSearchFilter.toLowerCase()) ||
      (p.concept_name || "").toLowerCase().includes(paramSearchFilter.toLowerCase()) ||
      p.account_puc.includes(paramSearchFilter) ||
      p.account_name.toLowerCase().includes(paramSearchFilter.toLowerCase())
  );

  const creditsRemaining = orgSubscription
    ? Math.max(0, (orgSubscription.credits_allocated || 0) - (orgSubscription.credits_used || 0))
    : 0;

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* SIDEBAR NAVEGACIÓN PERMANENTE */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between flex-shrink-0 z-20">
        <div>
          <div className="p-6 flex items-center space-x-3 border-b border-slate-800">
            <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-xl border border-indigo-500/30">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-base text-white leading-tight">Causaciones DIAN</h1>
              <span className="text-xs text-indigo-400 font-medium">SaaS Enterprise v3.5</span>
            </div>
          </div>

          <nav className="mt-6 px-3 space-y-1">
            <div className="px-3 pb-2 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Módulos
            </div>

            <button
              type="button"
              onClick={() => setActiveTab("operacion")}
              className={`w-full flex items-center space-x-3 px-3 py-3 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                activeTab === "operacion"
                  ? "bg-indigo-600/20 text-indigo-400 border-r-4 border-indigo-600 font-semibold"
                  : "text-slate-400 hover:bg-slate-800/60"
              }`}
            >
              <Cpu className="w-5 h-5" />
              <span>1. Operación & Causación</span>
            </button>

            {canManageTenantTables && (
              <button
                type="button"
                onClick={() => setActiveTab("mantenimiento")}
                className={`w-full flex items-center space-x-3 px-3 py-3 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                  activeTab === "mantenimiento"
                    ? "bg-indigo-600/20 text-indigo-400 border-r-4 border-indigo-600 font-semibold"
                    : "text-slate-400 hover:bg-slate-800/60"
                }`}
              >
                <Database className="w-5 h-5" />
                <span>2. Mantenimiento de Tablas</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setActiveTab("exportacion")}
              className={`w-full flex items-center space-x-3 px-3 py-3 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                activeTab === "exportacion"
                  ? "bg-indigo-600/20 text-indigo-400 border-r-4 border-indigo-600 font-semibold"
                  : "text-slate-400 hover:bg-slate-800/60"
              }`}
            >
              <FileSpreadsheet className="w-5 h-5" />
              <span>3. Exportación Multi-ERP</span>
            </button>

            {isSuperAdmin && (
              <button
                type="button"
                onClick={() => {
                  setActiveTab("facturacion");
                  const token = localStorage.getItem("access_token") || "";
                  loadAllMaintenanceTables(token, "SUPER_ADMIN");
                }}
                className={`w-full flex items-center space-x-3 px-3 py-3 rounded-xl text-sm font-medium transition-all cursor-pointer ${
                  activeTab === "facturacion"
                    ? "bg-emerald-600/20 text-emerald-400 border-r-4 border-emerald-500 font-semibold"
                    : "text-slate-400 hover:bg-slate-800/60"
                }`}
              >
                <Receipt className="w-5 h-5" />
                <span>4. Facturación SaaS</span>
              </button>
            )}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3 overflow-hidden">
              <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-white text-xs shrink-0">
                {(currentUser?.full_name || "PO").substring(0, 2).toUpperCase()}
              </div>
              <div className="overflow-hidden">
                <p className="text-xs font-semibold text-white truncate">
                  {currentUser?.full_name || "Usuario"}
                </p>
                <p className="text-[10px] text-indigo-400 font-mono truncate">
                  {currentUser?.role}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Cerrar Sesión"
              className="text-slate-400 hover:text-rose-400 transition-colors p-2 cursor-pointer"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </aside>

      {/* ÁREA DE CONTENIDO */}
      <main className="flex-1 flex flex-col overflow-y-auto bg-slate-950 z-10">
        <header className="h-16 border-b border-slate-800 bg-slate-900/40 px-8 flex items-center justify-between sticky top-0 z-10 backdrop-blur-md">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-2 animate-pulse"></span>
            Contexto: Multi-Tenant Unificado
          </span>
          <div className="text-right">
            <p className="text-xs text-slate-400">Organización Activa</p>
            <p className="text-xs font-semibold text-indigo-400">{activeOrgName}</p>
          </div>
        </header>

        <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">
          {/* ==================================================================
              MÓDULO 1: OPERACIÓN, CONTROL DE CRÉDITOS & CAUSACIÓN BAJO DEMANDA
             ================================================================== */}
          {activeTab === "operacion" && (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-bold text-white tracking-tight">
                    Centro de Operación & Causación DIAN
                  </h2>
                  <p className="text-sm text-slate-400">
                    Ingesta automatizada IMAP + Causación supervisada contra Matriz PUC.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={isSyncingEmails || !orgSubscription || creditsRemaining <= 0}
                  onClick={handleManualEmailSync}
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-4 py-2.5 rounded-xl text-sm font-medium flex items-center space-x-2 shadow-lg shadow-indigo-600/20 cursor-pointer"
                >
                  <RefreshCw className={`w-4 h-4 ${isSyncingEmails ? "animate-spin" : ""}`} />
                  <span>{isSyncingEmails ? "Sincronizando..." : "Sincronizar Correos Ahora"}</span>
                </button>
              </div>

              {/* ALERTA DE BLOQUEO SI NO HAY SUSCRIPCIÓN ACTIVA */}
              {(!orgSubscription || !orgSubscription.is_active || creditsRemaining <= 0) && (
                <div className="p-4 bg-rose-950/70 border border-rose-700/60 rounded-2xl flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 text-rose-200 text-xs">
                    <AlertTriangle className="w-6 h-6 text-rose-400 shrink-0" />
                    <div>
                      <p className="font-bold text-sm text-rose-100">
                        Descarga y Causación Bloqueadas por Suscripción
                      </p>
                      <p className="text-rose-300 mt-0.5">
                        Esta organización no cuenta con una suscripción activa o agotó sus créditos
                        disponibles. Debe activarse un plan en{" "}
                        <strong>Mantenimiento &gt; Suscripciones</strong> para bajar o causar
                        facturas.
                      </p>
                    </div>
                  </div>
                  {isSuperAdmin && (
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTab("mantenimiento");
                        setMaintenanceSubTab("subscriptions");
                      }}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-xl shrink-0 cursor-pointer"
                    >
                      Asignar Suscripción
                    </button>
                  )}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-slate-900/80 p-6 rounded-2xl border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Carga Manual XML/ZIP
                    </span>
                    <UploadCloud className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div className="mt-4 space-y-3">
                    <input
                      type="file"
                      accept=".xml,.zip"
                      onChange={(e) => setManualXmlFile(e.target.files?.[0] || null)}
                      className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600/20 file:text-indigo-400 cursor-pointer"
                    />
                    <button
                      type="button"
                      disabled={isUploadingManual || !orgSubscription || creditsRemaining <= 0}
                      onClick={handleManualXmlUpload}
                      className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-xs py-2 rounded-lg font-medium transition-colors cursor-pointer"
                    >
                      {isUploadingManual ? "Procesando XML..." : "Procesar Archivo"}
                    </button>
                  </div>
                </div>

                <div className="bg-slate-900/80 p-6 rounded-2xl border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Estado Scheduler & Facturas
                    </span>
                    <Activity className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div className="mt-4">
                    <span className="text-3xl font-extrabold text-white">
                      {invoicesList.length} Facturas
                    </span>
                    <p className="text-xs text-slate-400 mt-1">
                      Pendientes:{" "}
                      <strong className="text-amber-400">
                        {invoicesList.filter((i) => i.status === "PARSEADO").length}
                      </strong>{" "}
                      | Causadas:{" "}
                      <strong className="text-emerald-400">
                        {invoicesList.filter((i) => i.status === "CAUSADO").length}
                      </strong>
                    </p>
                  </div>
                </div>

                <div className="bg-slate-900/80 p-6 rounded-2xl border border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Créditos Disponibles
                    </span>
                    <Coins className="w-5 h-5 text-amber-400" />
                  </div>
                  <div className="mt-4">
                    {orgSubscription ? (
                      <>
                        <span
                          className={`text-3xl font-extrabold ${
                            creditsRemaining > 0 ? "text-amber-400" : "text-rose-400"
                          }`}
                        >
                          {creditsRemaining} / {orgSubscription.credits_allocated}
                        </span>
                        <p className="text-xs text-slate-400 mt-1">
                          Plan <strong>{orgSubscription.plan_name}</strong> (Usados:{" "}
                          {orgSubscription.credits_used || 0})
                        </p>
                      </>
                    ) : (
                      <>
                        <span className="text-2xl font-extrabold text-rose-400">0 (Sin Plan)</span>
                        <p className="text-xs text-slate-400 mt-1">
                          Requiere suscripción activa en BD.
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* BANDEJA DE FACTURAS CARGADAS Y CONTROLES DE CAUSACIÓN */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                <div className="p-5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Bandeja de Facturas Electrónicas DIAN ({invoicesList.length})
                    </h3>
                    <p className="text-xs text-slate-400">
                      Seleccione las facturas en estado PARSEADO para imputarlas contablemente.
                    </p>
                    
                    {/* BOTONES DE SELECCIÓN MASIVA */}
                    <div className="flex items-center gap-2 mt-3">
                      <button
                        type="button"
                        onClick={() => {
                          const parsedIds = invoicesList
                            .filter(i => i.status === "PARSEADO")
                            .map(i => i.id);
                          setSelectedInvoiceIds(parsedIds);
                        }}
                        className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                      >
                        Marcar todas (Parseadas)
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedInvoiceIds([])}
                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                      >
                        Deseleccionar todas
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <select
                      value={groupingMode}
                      onChange={(e) => setGroupingMode(e.target.value as any)}
                      className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                    >
                      <option value="CONSOLIDATED">Agrupación: Consolidada</option>
                      <option value="DETAILED">Agrupación: Detallada por Ítem</option>
                    </select>

                    <button
                      type="button"
                      disabled={isCausing || selectedInvoiceIds.length === 0}
                      onClick={handleCausarBatch}
                      className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      <span>
                        {isCausing
                          ? "Causando..."
                          : `Causar Seleccionadas (${selectedInvoiceIds.length})`}
                      </span>
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3.5 w-10">
                          {/* CHECKBOX MAESTRO EN CABECERA */}
                          <input
                            type="checkbox"
                            checked={
                              invoicesList.filter(i => i.status === "PARSEADO").length > 0 &&
                              invoicesList
                                .filter(i => i.status === "PARSEADO")
                                .every(i => selectedInvoiceIds.includes(i.id))
                            }
                            onChange={(e) => {
                              if (e.target.checked) {
                                const parsedIds = invoicesList
                                  .filter(i => i.status === "PARSEADO")
                                  .map(i => i.id);
                                setSelectedInvoiceIds(parsedIds);
                              } else {
                                setSelectedInvoiceIds([]);
                              }
                            }}
                            className="rounded bg-slate-950 border-slate-700 cursor-pointer"
                          />
                        </th>
                        <th className="px-4 py-3.5">Número</th>
                        <th className="px-4 py-3.5">Fecha</th>
                        <th className="px-4 py-3.5">Emisor / Tercero</th>
                        <th className="px-4 py-3.5 text-right">Subtotal</th>
                        <th className="px-4 py-3.5 text-right">Total a Pagar</th>
                        <th className="px-4 py-3.5 text-center">Estado</th>
                        <th className="px-4 py-3.5 text-right">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {invoicesList.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="px-6 py8 text-center text-slate-500">
                            No hay facturas registradas en esta organización.
                          </td>
                        </tr>
                      ) : (
                        invoicesList.map((inv) => (
                          <tr key={inv.id} className="hover:bg-slate-800/30">
                            <td className="px-4 py-3.5">
                              <input
                                type="checkbox"
                                checked={selectedInvoiceIds.includes(inv.id)}
                                onChange={() => toggleSelectInvoice(inv.id)}
                                className="rounded bg-slate-950 border-slate-700 cursor-pointer"
                              />
                            </td>
                            <td className="px-4 py-3.5 font-mono font-bold text-white">
                              {inv.full_number}
                            </td>
                            <td className="px-4 py-3.5 font-mono text-slate-400">
                              {inv.issue_date}
                            </td>
                            <td className="px-4 py-3.5">
                              <div className="font-semibold text-white">{inv.issuer_name}</div>
                              <div className="text-[10px] font-mono text-slate-400">
                                NIT: {inv.issuer_nit}
                              </div>
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono">
                              ${Number(inv.line_extension_amount || 0).toLocaleString("es-CO")}
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono font-bold text-indigo-300">
                              ${Number(inv.payable_amount || 0).toLocaleString("es-CO")}
                            </td>
                            <td className="px-4 py-3.5 text-center">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  inv.status === "CAUSADO"
                                    ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                                    : "bg-amber-950 text-amber-400 border border-amber-800/50"
                                }`}
                              >
                                {inv.status}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-right space-x-2 whitespace-nowrap">
                              <button
                                type="button"
                                disabled={isCausing}
                                onClick={() => handleCausarSingle(inv.id, inv.status)}
                                className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-[11px] font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                              >
                                <Eye className="w-3.5 h-3.5" />
                                <span>{inv.status === "CAUSADO" ? "Ver Asiento" : "Causar"}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenInvoiceDetails(inv.id)}
                                title="Ver Detalle y Validar DIAN"
                                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-[11px] font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                              >
                                <Receipt className="w-3.5 h-3.5 text-amber-400" />
                                <span>Ver DIAN</span>
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
			  
              {/* VISTA PREVIA DEL ASIENTO CONTABLE GENERADO */}
              {journalPreview && (
                <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-bold text-base text-white">
                        Comprobante Contable Causado — Factura {journalPreview.full_number}
                      </h4>
                      <p className="text-xs text-slate-400">
                        Modo: {journalPreview.grouping_mode} | Cuadre Partida Doble:{" "}
                        <strong
                          className={
                            journalPreview.is_balanced ? "text-emerald-400" : "text-rose-400"
                          }
                        >
                          {journalPreview.is_balanced ? "CUADRADO" : "DESCUADRADO"}
                        </strong>
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setJournalPreview(null)}
                      className="text-xs text-slate-400 hover:text-white cursor-pointer"
                    >
                      Cerrar Vista
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/70 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-4 py-2.5">Cuenta PUC</th>
                          <th className="px-4 py-2.5">Nombre Cuenta</th>
                          <th className="px-4 py-2.5">Tercero</th>
                          <th className="px-4 py-2.5">Detalle</th>
                          <th className="px-4 py-2.5 text-right">Débito</th>
                          <th className="px-4 py-2.5 text-right">Crédito</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {journalPreview.lines.map((line, idx) => (
                          <tr key={idx}>
                            <td className="px-4 py-2.5 font-mono font-bold text-indigo-300">
                              {line.account_puc}
                            </td>
                            <td className="px-4 py-2.5">{line.account_name}</td>
                            <td className="px-4 py-2.5 font-mono text-[11px]">
                              {line.third_party_nit}
                            </td>
                            <td className="px-4 py-2.5 text-slate-400">{line.description}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-emerald-400">
                              ${Number(line.debit).toLocaleString("es-CO")}
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-amber-400">
                              ${Number(line.credit).toLocaleString("es-CO")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      {/* PIE DE TABLA CON SUMAS Y DESCUADRE AUTOMÁTICO */}
                      <tfoot className="bg-slate-950 font-mono border-t border-slate-800">
                        <tr>
                          <td colSpan={4} className="px-4 py-3 text-right text-slate-400 uppercase text-[10px] font-bold">
                            Sumas Iguales:
                          </td>
                          <td className="px-4 py-3 text-right text-emerald-400 font-bold">
                            ${Number(journalPreview.total_debit).toLocaleString("es-CO")}
                          </td>
                          <td className="px-4 py-3 text-right text-amber-400 font-bold">
                            ${Number(journalPreview.total_credit).toLocaleString("es-CO")}
                          </td>
                        </tr>
                        {!journalPreview.is_balanced && (
                          <tr>
                            <td colSpan={6} className="px-4 py-2.5 text-center bg-rose-950/60 text-rose-300 text-xs font-sans">
                              <span className="font-bold">⚠️ DESCUADRE DETECTADO:</span>{" "}
                              <span className="font-mono font-bold text-rose-200">
                                ${Math.abs(journalPreview.total_debit - journalPreview.total_credit).toLocaleString("es-CO")}
                              </span>
                              <span className="ml-2 text-[11px] text-rose-400">
                                (Diferencia atribuible al manejo de retenciones informativas / neto a pagar)
                              </span>
                            </td>
                          </tr>
                        )}
                      </tfoot>
                    </table>
                  </div>
				  
				  
                </div>
              )}
			  
			  
			  
            </div>
          )}

		  {/* MODAL VISOR DE FACTURA DIAN & ÍTEMS */}
        {invoiceDetailModal && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden shadow-2xl">
              <div className="p-6 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Receipt className="w-5 h-5 text-indigo-400" />
                    Factura Electrónica DIAN — {invoiceDetailModal.invoice.full_number}
                  </h3>
                  
                  {/* SECCIÓN CUFE CON BOTÓN DE COPIAR */}
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-xs text-slate-400 font-mono truncate max-w-lg">
                      CUFE: {invoiceDetailModal.invoice.cufe}
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(invoiceDetailModal.invoice.cufe);
                        alert("¡CUFE copiado al portapapeles!");
                      }}
                      className="px-2 py-0.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded text-[10px] font-semibold transition-colors shrink-0 cursor-pointer"
                    >
                      Copiar CUFE
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setInvoiceDetailModal(null)}
                  className="p-2 text-slate-400 hover:text-white rounded-xl bg-slate-800/60 cursor-pointer"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
			  <div className="p-6 overflow-y-auto space-y-6">
                {/* Emisor / Receptor */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div>
                    <span className="text-slate-500 uppercase text-[10px] font-bold block">Emisor</span>
                    <p className="font-bold text-white text-sm">{invoiceDetailModal.invoice.issuer_name}</p>
                    <p className="font-mono text-slate-400">NIT: {invoiceDetailModal.invoice.issuer_nit}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 uppercase text-[10px] font-bold block">Receptor</span>
                    <p className="font-bold text-white text-sm">{invoiceDetailModal.invoice.receiver_name}</p>
                    <p className="font-mono text-slate-400">NIT: {invoiceDetailModal.invoice.receiver_nit}</p>
                  </div>
                </div>

                {/* Tabla de Ítems */}
                <div>
                  <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
                    Ítems / Detalle de la Factura ({invoiceDetailModal.items.length})
                  </h4>
                  <div className="overflow-x-auto border border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950 uppercase text-[10px] text-slate-500 border-b border-slate-800">
                        <tr>
                          <th className="px-3 py-2">#</th>
                          <th className="px-3 py-2">UNSPSC / Ref</th>
                          <th className="px-3 py-2">Descripción</th>
                          <th className="px-3 py-2 text-right">Cant.</th>
                          <th className="px-3 py-2 text-right">V. Unitario</th>
                          <th className="px-3 py-2 text-right">Subtotal</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/50">
                        {invoiceDetailModal.items.map((item: any, idx: number) => (
                          <tr key={item.id || idx}>
                            <td className="px-3 py-2 font-mono">{item.line_number}</td>
                            <td className="px-3 py-2 font-mono text-indigo-300">
                              {item.unspsc_code || item.seller_item_id || "-"}
                            </td>
                            <td className="px-3 py-2 text-slate-200">{item.description}</td>
                            <td className="px-3 py-2 text-right font-mono">{item.quantity}</td>
                            <td className="px-3 py-2 text-right font-mono">
                              ${Number(item.unit_price || 0).toLocaleString("es-CO")}
                            </td>
                            <td className="px-3 py-2 text-right font-mono font-bold text-white">
                              ${Number(item.subtotal || 0).toLocaleString("es-CO")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {invoiceDetailModal.taxes.length > 0 && (
				  <div>
					<h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
					Impuestos y Retenciones
					</h4>
					<div className="overflow-x-auto border border-slate-800 rounded-xl">
					  <table className="w-full text-left text-xs text-slate-300">
						<thead className="bg-slate-950 uppercase text-[10px] text-slate-500 border-b border-slate-800">
						<tr>
							<th className="px-3 py-2">Tipo</th>
							<th className="px-3 py-2 text-right">Porcentaje</th>
							<th className="px-3 py-2 text-right">Base Gravable</th>
							<th className="px-3 py-2 text-right">Valor Impuesto</th>
						</tr>
					  </thead>
					  <tbody className="divide-y divide-slate-800/50">
						{invoiceDetailModal.taxes.map((tax: any, idx: number) => (
							<tr key={tax.id || idx}>
								<td className="px-3 py-2 font-semibold text-white">{tax.type}</td>
								<td className="px-3 py-2 text-right font-mono">{tax.percent}%</td>
								<td className="px-3 py-2 text-right font-mono">
								 ${Number(tax.taxable_amount || 0).toLocaleString("es-CO")}
								</td>
								<td className="px-3 py-2 text-right font-mono text-amber-400">
								 ${Number(tax.tax_amount || 0).toLocaleString("es-CO")}
								</td>
							</tr>
						))}
						</tbody>
					  </table>
					</div>
				  </div>
				)}
				
                {/* Totales y Enlace Directo al Portal DIAN por CUFE */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs text-slate-400">
                      Total a Pagar:{" "}
                      <strong className="text-emerald-400 font-mono text-base">
                        ${Number(invoiceDetailModal.invoice.payable_amount || 0).toLocaleString("es-CO")} {invoiceDetailModal.invoice.currency || "COP"}
                      </strong>
                    </p>
                  </div>
                  <div className="flex gap-3">
                    <a
                      href={`https://catalogo-vpfe.dian.gov.co/document/search?documentKey=${invoiceDetailModal.invoice.cufe}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold inline-flex items-center gap-2 transition-colors"
                    >
                      <span>Validar en Portal DIAN (CUFE)</span>
                    </a>
                    <button
                      type="button"
                      onClick={() => setInvoiceDetailModal(null)}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold cursor-pointer"
                    >
                      Cerrar
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}


          {/* ==================================================================
              MÓDULO 2: MANTENIMIENTO DE TABLAS
             ================================================================== */}
          {activeTab === "mantenimiento" && canManageTenantTables && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-white tracking-tight">
                    Mantenimiento de Tablas del Sistema
                  </h2>
                  <p className="text-sm text-slate-400">
                    Gestión estructurada de tablas maestras con operaciones CRUD completas (Crear,
                    Editar y Eliminar).
                  </p>
                </div>
              </div>

              {/* BARRA DE SUB-PESTAÑAS SEGÚN ROL */}
              <div className="flex space-x-2 border-b border-slate-800 pb-3 overflow-x-auto">
                {isSuperAdmin && (
                  <button
                    type="button"
                    onClick={() => {
                      setMaintenanceSubTab("organizations");
                      setShowOrgForm(false);
                      setEditingOrgId(null);
                    }}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                      maintenanceSubTab === "organizations"
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                    }`}
                  >
                    <Building className="w-4 h-4" />
                    <span>Organizaciones (organizations)</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    setMaintenanceSubTab("users");
                    setShowUserForm(false);
                    setEditingUserId(null);
                  }}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                    maintenanceSubTab === "users"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  <UserCheck className="w-4 h-4" />
                  <span>Usuarios (users_profile)</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMaintenanceSubTab("companies");
                    setShowCompanyForm(false);
                    setEditingCompanyId(null);
                  }}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                    maintenanceSubTab === "companies"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  <Building2 className="w-4 h-4" />
                  <span>Excepciones NIT (companies)</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMaintenanceSubTab("accounting");
                    setShowParamForm(false);
                    setEditingParamId(null);
                  }}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                    maintenanceSubTab === "accounting"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  <Calculator className="w-4 h-4" />
                  <span>Parámetros Contables (PUC / DIAN)</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMaintenanceSubTab("emails");
                    setShowEmailForm(false);
                    setEditingEmailId(null);
                  }}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                    maintenanceSubTab === "emails"
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                  }`}
                >
                  <Server className="w-4 h-4" />
                  <span>Correos IMAP (company_email_integrations)</span>
                </button>

                {isSuperAdmin && (
                  <button
                    type="button"
                    onClick={() => {
                      setMaintenanceSubTab("subscriptions");
                      setShowSubForm(false);
                      setEditingSubId(null);
                    }}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                      maintenanceSubTab === "subscriptions"
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                    }`}
                  >
                    <CreditCard className="w-4 h-4" />
                    <span>Suscripciones (company_subscriptions)</span>
                  </button>
                )}
				
				{isSuperAdmin && (
                  <button
                    type="button"
                    onClick={() => {
                      setMaintenanceSubTab("plans");
                      setShowPlanForm(false);
                      setEditingPlanId(null);
                    }}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer whitespace-nowrap ${
                      maintenanceSubTab === "plans"
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-900 text-slate-400 hover:bg-slate-800"
                    }`}
                  >
                    <Coins className="w-4 h-4" />
                    <span>Planes Comerciales (subscription_plans)</span>
                  </button>
                )}
				
              </div>

              {/* 1. ORGANIZACIONES */}
              {maintenanceSubTab === "organizations" && isSuperAdmin && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300">
                      Organizaciones Clientes del SaaS (Dueñas de Cuenta)
                    </h3>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingOrgId(null);
                        setOrgFormData({ name: "", nit: "" });
                        setShowOrgForm(!showOrgForm);
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
                    >
                      <Plus className="w-4 h-4" />
                      <span>{showOrgForm ? "Cerrar Formulario" : "Nueva Organización"}</span>
                    </button>
                  </div>

                  {showOrgForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingOrgId
                          ? "Editar Organización Matriz"
                          : "Registrar Nueva Organización Matriz"}
                      </h4>
                      <form onSubmit={handleSaveOrganization} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Razón Social</label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: POSSAR SALES GLOBAL"
                              value={orgFormData.name}
                              onChange={(e) =>
                                setOrgFormData({ ...orgFormData, name: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">NIT</label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: 900800800"
                              value={orgFormData.nit}
                              onChange={(e) =>
                                setOrgFormData({ ...orgFormData, nit: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowOrgForm(false);
                              setEditingOrgId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs rounded-xl hover:bg-slate-700 cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            disabled={isSavingOrg}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold rounded-xl flex items-center gap-2 cursor-pointer disabled:opacity-50"
                          >
                            {isSavingOrg ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : editingOrgId ? (
                              "Actualizar Organización"
                            ) : (
                              "Guardar Organización"
                            )}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-6 py-3.5">Razón Social</th>
                          <th className="px-6 py-3.5">NIT</th>
                          <th className="px-6 py-3.5">ID Único (UUID)</th>
                          <th className="px-6 py-3.5">Estado</th>
                          <th className="px-6 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {organizationsList.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                              No hay organizaciones registradas.
                            </td>
                          </tr>
                        ) : (
                          organizationsList.map((o) => (
                            <tr key={o.id} className="hover:bg-slate-800/30">
                              <td className="px-6 py-4 font-semibold text-white">{o.name}</td>
                              <td className="px-6 py-4 font-mono text-slate-400">{o.nit}</td>
                              <td className="px-6 py-4 font-mono text-[11px] text-indigo-400">
                                {o.id}
                              </td>
                              <td className="px-6 py-4">
                                <span className="text-emerald-400 font-semibold">Activa</span>
                              </td>
                              <td className="px-6 py-4 text-right space-x-2">
                                <button
                                  type="button"
                                  onClick={() => handleEditOrganization(o)}
                                  title="Editar Organización"
                                  className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteOrganization(o.id, o.name)}
                                  title="Eliminar Organización"
                                  className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 2. USUARIOS */}
              {maintenanceSubTab === "users" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300">
                      Gestión de Perfiles y Roles de la Organización
                    </h3>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingUserId(null);
                        setUserFormData({
                          full_name: "",
                          email: "",
                          password: "",
                          role: isSuperAdmin ? "COMPANY_ADMIN" : "COMPANY_OPERATOR"
                        });
                        setShowUserForm(!showUserForm);
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
                    >
                      <Plus className="w-4 h-4" />
                      <span>{showUserForm ? "Cerrar Formulario" : "Nuevo Usuario"}</span>
                    </button>
                  </div>

                  {showUserForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingUserId ? "Editar Perfil de Usuario" : "Ingresar Nuevo Usuario"}
                      </h4>

                      <div className="p-3 bg-indigo-950/60 border border-indigo-800/50 rounded-xl flex items-center justify-between text-xs">
                        <span className="text-slate-400">
                          Organización Asignada (Heredada de Sesión):
                        </span>
                        <span className="font-bold text-indigo-300 font-mono">{activeOrgName}</span>
                      </div>

                      <form onSubmit={handleSaveUser} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <input
                            type="text"
                            required
                            placeholder="Nombre Completo"
                            value={userFormData.full_name}
                            onChange={(e) =>
                              setUserFormData({ ...userFormData, full_name: e.target.value })
                            }
                            className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                          />
                          <input
                            type="email"
                            required
                            placeholder="Correo Electrónico"
                            value={userFormData.email}
                            onChange={(e) =>
                              setUserFormData({ ...userFormData, email: e.target.value })
                            }
                            className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <input
                            type="password"
                            required={!editingUserId}
                            placeholder={
                              editingUserId
                                ? "Nueva Contraseña (dejar vacío para mantener)"
                                : "Contraseña"
                            }
                            value={userFormData.password}
                            onChange={(e) =>
                              setUserFormData({ ...userFormData, password: e.target.value })
                            }
                            className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                          />
                          <select
                            value={userFormData.role}
                            onChange={(e) =>
                              setUserFormData({
                                ...userFormData,
                                role: e.target.value as any
                              })
                            }
                            className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                          >
                            {isSuperAdmin && (
                              <option value="COMPANY_ADMIN">
                                COMPANY_ADMIN (Administrador Cliente)
                              </option>
                            )}
                            <option value="COMPANY_OPERATOR">
                              COMPANY_OPERATOR (Operador Causaciones)
                            </option>
                            <option value="COMPANY_EXPORTER">
                              COMPANY_EXPORTER (Exportador ERP)
                            </option>
                          </select>
                        </div>
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowUserForm(false);
                              setEditingUserId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-xs text-slate-300 rounded-xl cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            className="px-4 py-2 bg-indigo-600 text-xs text-white font-semibold rounded-xl cursor-pointer"
                          >
                            {editingUserId ? "Actualizar Usuario" : "Guardar Usuario"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-6 py-3.5">Nombre Completo</th>
                          <th className="px-6 py-3.5">Email</th>
                          <th className="px-6 py-3.5">Rol</th>
                          <th className="px-6 py-3.5">Estado</th>
                          <th className="px-6 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {usersList.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                              No hay usuarios registrados en esta organización.
                            </td>
                          </tr>
                        ) : (
                          usersList.map((u) => (
                            <tr key={u.id} className="hover:bg-slate-800/30">
                              <td className="px-6 py-4 font-semibold text-white">{u.full_name}</td>
                              <td className="px-6 py-4 font-mono text-slate-400">{u.email}</td>
                              <td className="px-6 py-4">
                                <span className="px-2 py-1 bg-indigo-950 text-indigo-300 rounded text-[10px] font-mono">
                                  {u.role}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <span className="text-emerald-400 font-semibold">Activo</span>
                              </td>
                              <td className="px-6 py-4 text-right space-x-2">
                                <button
                                  type="button"
                                  onClick={() => handleEditUser(u)}
                                  title="Editar Usuario"
                                  className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteUser(u.id, u.full_name)}
                                  title="Eliminar Usuario"
                                  className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 3. EXCEPCIONES NIT */}
              {maintenanceSubTab === "companies" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300">
                      Directorio de Excepciones de NIT (companies)
                    </h3>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingCompanyId(null);
                        setCompanyFormData({ name: "", nit: "" });
                        setShowCompanyForm(!showCompanyForm);
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
                    >
                      <Plus className="w-4 h-4" />
                      <span>{showCompanyForm ? "Cerrar Formulario" : "Nueva Excepción NIT"}</span>
                    </button>
                  </div>

                  {showCompanyForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingCompanyId ? "Editar Excepción de NIT" : "Ingresar Excepción de NIT"}
                      </h4>
                      <form onSubmit={handleSaveCompany} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Razón Social</label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: PROVEEDOR EXCEPCIÓN 1"
                              value={companyFormData.name}
                              onChange={(e) =>
                                setCompanyFormData({ ...companyFormData, name: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">NIT</label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: 900123456"
                              value={companyFormData.nit}
                              onChange={(e) =>
                                setCompanyFormData({ ...companyFormData, nit: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowCompanyForm(false);
                              setEditingCompanyId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs rounded-xl hover:bg-slate-700 cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            disabled={isSavingCompany}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold rounded-xl flex items-center gap-2 cursor-pointer disabled:opacity-50"
                          >
                            {isSavingCompany ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : editingCompanyId ? (
                              "Actualizar Excepción"
                            ) : (
                              "Guardar Excepción"
                            )}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-6 py-3.5">Razón Social</th>
                          <th className="px-6 py-3.5">NIT</th>
                          <th className="px-6 py-3.5">Estado</th>
                          <th className="px-6 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {companiesList.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                              No hay excepciones de NIT registradas en esta organización.
                            </td>
                          </tr>
                        ) : (
                          companiesList.map((c) => (
                            <tr key={c.id} className="hover:bg-slate-800/30">
                              <td className="px-6 py-4 font-semibold text-white">{c.name}</td>
                              <td className="px-6 py-4 font-mono text-slate-400">{c.nit}</td>
                              <td className="px-6 py-4">
                                <span className="text-emerald-400 font-semibold">Activa</span>
                              </td>
                              <td className="px-6 py-4 text-right space-x-2">
                                <button
                                  type="button"
                                  onClick={() => handleEditCompany(c)}
                                  title="Editar Excepción NIT"
                                  className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteCompany(c.id, c.name)}
                                  title="Eliminar Excepción NIT"
                                  className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 4. PARÁMETROS CONTABLES PUC / DIAN */}
              {maintenanceSubTab === "accounting" && (
                <div className="space-y-4">
                  <div className="flex flex-wrap justify-between items-center gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-300">
                        Matriz de Parametrización Contable PUC / DIAN (
                        {accountingParamsList.length} conceptos)
                      </h3>
                    </div>

                    <div className="flex items-center gap-3">
                      <input
                        type="text"
                        placeholder="Buscar código, PUC o descripción..."
                        value={paramSearchFilter}
                        onChange={(e) => setParamSearchFilter(e.target.value)}
                        className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 w-64"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          setEditingParamId(null);
                          setParamFormData({
                            concept_code: "",
                            concept_name: "",
                            account_puc: "",
                            account_name: "",
                            nature: "D"
                          });
                          setShowParamForm(!showParamForm);
                        }}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
                      >
                        <Plus className="w-4 h-4" />
                        <span>{showParamForm ? "Cerrar Formulario" : "Nuevo Parámetro PUC"}</span>
                      </button>
                    </div>
                  </div>

                  {showParamForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingParamId
                          ? "Editar Parámetro Contable PUC"
                          : "Nuevo Parámetro Contable PUC"}
                      </h4>
                      <form onSubmit={handleSaveAccountingParam} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Código Concepto DIAN
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: RETEFUENTE_COMPRAS_2.5"
                              value={paramFormData.concept_code}
                              onChange={(e) =>
                                setParamFormData({ ...paramFormData, concept_code: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Cuenta PUC
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: 23654025"
                              value={paramFormData.account_puc}
                              onChange={(e) =>
                                setParamFormData({ ...paramFormData, account_puc: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Naturaleza Contable
                            </label>
                            <select
                              value={paramFormData.nature}
                              onChange={(e) =>
                                setParamFormData({
                                  ...paramFormData,
                                  nature: e.target.value as "D" | "C"
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            >
                              <option value="D">D - Débito</option>
                              <option value="C">C - Crédito</option>
                            </select>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Descripción del Concepto Tributario
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: Retefuente Compras Generales (Declarantes 2.5%)"
                              value={paramFormData.concept_name}
                              onChange={(e) =>
                                setParamFormData({ ...paramFormData, concept_name: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Nombre de la Cuenta PUC
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: ReteFuente Compras Declarantes 2.5%"
                              value={paramFormData.account_name}
                              onChange={(e) =>
                                setParamFormData({ ...paramFormData, account_name: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            />
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowParamForm(false);
                              setEditingParamId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs rounded-xl cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold rounded-xl cursor-pointer"
                          >
                            {editingParamId ? "Actualizar Parámetro" : "Guardar Parámetro"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-4 py-3.5">Código Concepto</th>
                          <th className="px-4 py-3.5">Descripción Tributaria</th>
                          <th className="px-4 py-3.5">Cuenta PUC</th>
                          <th className="px-4 py-3.5">Nombre Cuenta PUC</th>
                          <th className="px-4 py-3.5 text-center">Nat.</th>
                          <th className="px-4 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {filteredParams.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                              No se encontraron parámetros contables para esta organización.
                            </td>
                          </tr>
                        ) : (
                          filteredParams.map((p) => (
                            <tr key={p.id} className="hover:bg-slate-800/30">
                              <td className="px-4 py-3 font-mono font-semibold text-indigo-300">
                                {p.concept_code}
                              </td>
                              <td className="px-4 py-3 text-slate-300">{p.concept_name}</td>
                              <td className="px-4 py-3 font-mono font-bold text-white">
                                {p.account_puc}
                              </td>
                              <td className="px-4 py-3 text-slate-400">{p.account_name}</td>
                              <td className="px-4 py-3 text-center">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    p.nature === "D"
                                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                                      : "bg-amber-950 text-amber-400 border border-amber-800/50"
                                  }`}
                                >
                                  {p.nature === "D" ? "DÉBITO" : "CRÉDITO"}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                                <button
                                  type="button"
                                  onClick={() => handleEditAccountingParam(p)}
                                  title="Editar Parámetro Contable"
                                  className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteAccountingParam(p.id, p.concept_code)}
                                  title="Eliminar Parámetro Contable"
                                  className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 5. CORREOS IMAP */}
              {maintenanceSubTab === "emails" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300">
                      Cuentas de Correo IMAP para Ingesta Automática DIAN (
                      {emailIntegrationsList.length} configuradas)
                    </h3>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingEmailId(null);
                        setEmailFormData({
                          direction: "RECIBIDA",
                          imap_server: "imap.gmail.com",
                          imap_port: 993,
                          email_account: "",
                          email_password: "",
                          folder_name: "INBOX",
                          scan_frequency_minutes: 15,
                          is_active: true
                        });
                        setShowEmailForm(!showEmailForm);
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
                    >
                      <Plus className="w-4 h-4" />
                      <span>{showEmailForm ? "Cerrar Formulario" : "Nueva Cuenta IMAP"}</span>
                    </button>
                  </div>

                  {showEmailForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingEmailId
                          ? "Editar Integración de Correo IMAP"
                          : "Registrar Nueva Cuenta de Correo IMAP"}
                      </h4>

                      <div className="p-3 bg-indigo-950/60 border border-indigo-800/50 rounded-xl flex items-center justify-between text-xs">
                        <span className="text-slate-400">Organización Vinculada:</span>
                        <span className="font-bold text-indigo-300 font-mono">{activeOrgName}</span>
                      </div>

                      <form onSubmit={handleSaveEmailIntegration} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Dirección Flujo Facturas
                            </label>
                            <select
                              value={emailFormData.direction}
                              onChange={(e) =>
                                setEmailFormData({
                                  ...emailFormData,
                                  direction: e.target.value as "RECIBIDA" | "EMITIDA"
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            >
                              <option value="RECIBIDA">RECIBIDA (Compras / Proveedores)</option>
                              <option value="EMITIDA">EMITIDA (Ventas / Clientes)</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Servidor IMAP
                            </label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: imap.gmail.com"
                              value={emailFormData.imap_server}
                              onChange={(e) =>
                                setEmailFormData({ ...emailFormData, imap_server: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Puerto SSL</label>
                            <input
                              type="number"
                              required
                              value={emailFormData.imap_port}
                              onChange={(e) =>
                                setEmailFormData({
                                  ...emailFormData,
                                  imap_port: parseInt(e.target.value) || 993
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Cuenta de Correo
                            </label>
                            <input
                              type="email"
                              required
                              placeholder="facturacion@empresa.com"
                              value={emailFormData.email_account}
                              onChange={(e) =>
                                setEmailFormData({
                                  ...emailFormData,
                                  email_account: e.target.value
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Contraseña / App Password
                            </label>
                            <input
                              type="password"
                              required={!editingEmailId}
                              placeholder={
                                editingEmailId
                                  ? "Dejar vacío para mantener contraseña actual"
                                  : "••••••••••••"
                              }
                              value={emailFormData.email_password}
                              onChange={(e) =>
                                setEmailFormData({
                                  ...emailFormData,
                                  email_password: e.target.value
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Carpeta Buzón & Estado
                            </label>
                            <div className="flex gap-2">
                              <input
                                type="text"
                                required
                                placeholder="INBOX"
                                value={emailFormData.folder_name}
                                onChange={(e) =>
                                  setEmailFormData({
                                    ...emailFormData,
                                    folder_name: e.target.value
                                  })
                                }
                                className="w-1/2 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                              />
                              <select
                                value={emailFormData.is_active ? "true" : "false"}
                                onChange={(e) =>
                                  setEmailFormData({
                                    ...emailFormData,
                                    is_active: e.target.value === "true"
                                  })
                                }
                                className="w-1/2 bg-slate-950 border border-slate-700 rounded-xl px-2 py-2 text-xs text-white"
                              >
                                <option value="true">Activo</option>
                                <option value="false">Inactivo</option>
                              </select>
                            </div>
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowEmailForm(false);
                              setEditingEmailId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs rounded-xl cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold rounded-xl cursor-pointer"
                          >
                            {editingEmailId ? "Actualizar Cuenta IMAP" : "Guardar Cuenta IMAP"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-5 py-3.5">Flujo</th>
                          <th className="px-5 py-3.5">Cuenta de Correo</th>
                          <th className="px-5 py-3.5">Servidor IMAP : Puerto</th>
                          <th className="px-5 py-3.5">Carpeta</th>
                          <th className="px-5 py-3.5">Estado</th>
                          <th className="px-5 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {emailIntegrationsList.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                              No hay cuentas de correo IMAP configuradas para esta organización.
                            </td>
                          </tr>
                        ) : (
                          emailIntegrationsList.map((item) => (
                            <tr key={item.id} className="hover:bg-slate-800/30">
                              <td className="px-5 py-4">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    item.direction === "RECIBIDA"
                                      ? "bg-indigo-950 text-indigo-300 border border-indigo-800/50"
                                      : "bg-purple-950 text-purple-300 border border-purple-800/50"
                                  }`}
                                >
                                  {item.direction}
                                </span>
                              </td>
                              <td className="px-5 py-4 font-semibold text-white">
                                {item.email_account}
                              </td>
                              <td className="px-5 py-4 font-mono text-slate-400">
                                {item.imap_server}:{item.imap_port}
                              </td>
                              <td className="px-5 py-4 font-mono text-xs text-slate-300">
                                {item.folder_name}
                              </td>
                              <td className="px-5 py-4">
                                <span
                                  className={`font-semibold ${
                                    item.is_active ? "text-emerald-400" : "text-rose-400"
                                  }`}
                                >
                                  {item.is_active ? "Activa" : "Inactiva"}
                                </span>
                              </td>
                              <td className="px-5 py-4 text-right space-x-2">
                                <button
                                  type="button"
                                  onClick={() => handleEditEmailIntegration(item)}
                                  title="Editar Cuenta IMAP"
                                  className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() =>
                                    handleDeleteEmailIntegration(item.id, item.email_account)
                                  }
                                  title="Eliminar Cuenta IMAP"
                                  className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 6. SUSCRIPCIONES COMPLETO (SOLO SUPER_ADMIN) */}
              {maintenanceSubTab === "subscriptions" && isSuperAdmin && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300">
                      Control de Planes, Créditos y Tarifas por Organización
                    </h3>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingSubId(null);
                        setSubFormData({
                          organization_id: currentUser?.organization_id || "",
                          plan_name: "ENTERPRISE",
                          credits_allocated: 1000,
                          credits_used: 0,
                          monthly_fee: 150000,
                          billing_cycle: "MONTHLY",
                          start_date: new Date().toISOString().slice(0, 10),
                          end_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
                          is_active: true
                        });
                        setShowSubForm(!showSubForm);
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer"
                    >
                      <Plus className="w-4 h-4" />
                      <span>{showSubForm ? "Cerrar Formulario" : "Nueva Suscripción"}</span>
                    </button>
                  </div>

                  {showSubForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingSubId
                          ? "Editar Suscripción Comercial"
                          : "Asignar Nueva Suscripción Comercial"}
                      </h4>
                      <form onSubmit={handleSaveSubscription} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Organización Cliente
                            </label>
                            <select
                              required
                              value={subFormData.organization_id}
                              onChange={(e) =>
                                setSubFormData({ ...subFormData, organization_id: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            >
                              <option value="">-- Seleccione Organización --</option>
                              {organizationsList.map((o) => (
                                <option key={o.id} value={o.id}>
                                  {o.name}
                                </option>
                              ))}
                            </select>
                          </div>
						  <div>
                            <label className="block text-xs text-slate-400 mb-1">Plan Comercial SaaS</label>
                            <select
                              required
                              value={subFormData.plan_name}
                              onChange={(e) => {
                                const selectedCode = e.target.value;
                                const foundPlan = subscriptionPlansList.find(p => p.code === selectedCode);
                                if (foundPlan) {
                                  setSubFormData({
                                    ...subFormData,
                                    plan_name: foundPlan.code,
                                    credits_allocated: foundPlan.credits_allocated,
                                    monthly_fee: foundPlan.monthly_fee
                                  });
                                } else {
                                  setSubFormData({ ...subFormData, plan_name: selectedCode });
                                }
                              }}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            >
                              <option value="">-- Seleccione Plan --</option>
                              {subscriptionPlansList.map((plan) => (
                                <option key={plan.id} value={plan.code}>
                                  {plan.name} ({plan.credits_allocated} créditos - ${Number(plan.monthly_fee).toLocaleString("es-CO")} COP)
                                </option>
                              ))}
                            </select>
                          </div>                         
						  <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Créditos Asignados
                            </label>
                            <input
                              type="number"
                              required
                              value={subFormData.credits_allocated}
                              onChange={(e) =>
                                setSubFormData({
                                  ...subFormData,
                                  credits_allocated: parseInt(e.target.value) || 0
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Créditos Consumidos
                            </label>
                            <input
                              type="number"
                              required
                              value={subFormData.credits_used}
                              onChange={(e) =>
                                setSubFormData({
                                  ...subFormData,
                                  credits_used: parseInt(e.target.value) || 0
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Valor Plan (COP)
                            </label>
                            <input
                              type="number"
                              required
                              value={subFormData.monthly_fee}
                              onChange={(e) =>
                                setSubFormData({
                                  ...subFormData,
                                  monthly_fee: parseFloat(e.target.value) || 0
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Fecha Inicio
                            </label>
                            <input
                              type="date"
                              value={subFormData.start_date}
                              onChange={(e) =>
                                setSubFormData({ ...subFormData, start_date: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">
                              Fecha Corte / Vencimiento
                            </label>
                            <input
                              type="date"
                              value={subFormData.end_date}
                              onChange={(e) =>
                                setSubFormData({ ...subFormData, end_date: e.target.value })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Estado</label>
                            <select
                              value={subFormData.is_active ? "true" : "false"}
                              onChange={(e) =>
                                setSubFormData({
                                  ...subFormData,
                                  is_active: e.target.value === "true"
                                })
                              }
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            >
                              <option value="true">Activa (Habilitada)</option>
                              <option value="false">Suspendida / Inactiva</option>
                            </select>
                          </div>
                        </div>

                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowSubForm(false);
                              setEditingSubId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-xs text-slate-300 rounded-xl cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            className="px-4 py-2 bg-indigo-600 text-xs text-white font-semibold rounded-xl cursor-pointer"
                          >
                            {editingSubId ? "Actualizar Suscripción" : "Guardar Suscripción"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-5 py-3.5">Organización</th>
                          <th className="px-5 py-3.5">Plan</th>
                          <th className="px-5 py-3.5 text-right">Asignados</th>
                          <th className="px-5 py-3.5 text-right">Usados</th>
                          <th className="px-5 py-3.5 text-right">Disponibles</th>
                          <th className="px-5 py-3.5 text-right">Tarifa Mensual</th>
                          <th className="px-5 py-3.5">Vencimiento</th>
                          <th className="px-5 py-3.5">Estado</th>
                          <th className="px-5 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {subscriptionsList.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="px-6 py-8 text-center text-slate-500">
                              No hay suscripciones registradas. Ninguna organización podrá bajar ni
                              causar facturas hasta asignar un plan.
                            </td>
                          </tr>
                        ) : (
                          subscriptionsList.map((s) => {
                            const orgName =
                              s.organizations?.name ||
                              organizationsList.find((o) => o.id === s.organization_id)?.name ||
                              "Organización";
                            const rem = Math.max(
                              0,
                              (s.credits_allocated || 0) - (s.credits_used || 0)
                            );
                            return (
                              <tr key={s.id} className="hover:bg-slate-800/30">
                                <td className="px-5 py-4 font-semibold text-white">{orgName}</td>
                                <td className="px-5 py-4 font-mono text-indigo-400">
                                  {s.plan_name}
                                </td>
                                <td className="px-5 py-4 text-right font-mono">
                                  {s.credits_allocated}
                                </td>
                                <td className="px-5 py-4 text-right font-mono text-slate-400">
                                  {s.credits_used || 0}
                                </td>
                                <td className="px-5 py-4 text-right font-mono font-bold text-amber-400">
                                  {rem}
                                </td>
                                <td className="px-5 py-4 text-right font-mono text-emerald-400">
                                  ${Number(s.monthly_fee || 0).toLocaleString("es-CO")}
                                </td>
                                <td className="px-5 py-4 font-mono text-slate-400">
                                  {s.end_date || "-"}
                                </td>
                                <td className="px-5 py-4">
                                  <span
                                    className={`font-semibold ${
                                      s.is_active ? "text-emerald-400" : "text-rose-400"
                                    }`}
                                  >
                                    {s.is_active ? "Activa" : "Inactiva"}
                                  </span>
                                </td>
                                <td className="px-5 py-4 text-right space-x-2 whitespace-nowrap">
                                  <button
                                    type="button"
                                    onClick={() => handleEditSubscription(s)}
                                    title="Editar Suscripción"
                                    className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                  >
                                    <Edit className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteSubscription(s.id)}
                                    title="Eliminar Suscripción"
                                    className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
////*****
{/* 7. PLANES COMERCIALES (SOLO SUPER_ADMIN) */}
              {maintenanceSubTab === "plans" && isSuperAdmin && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300">
                      Catálogo de Planes Comerciales SaaS (subscription_plans)
                    </h3>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingPlanId(null);
                        setPlanFormData({
                          code: "",
                          name: "",
                          credits_allocated: 1000,
                          monthly_fee: 150000,
                          additional_credit_fee: 150,
                          is_active: true
                        });
                        setShowPlanForm(!showPlanForm);
                      }}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
                    >
                      <Plus className="w-4 h-4" />
                      <span>{showPlanForm ? "Cerrar Formulario" : "Nuevo Plan Comercial"}</span>
                    </button>
                  </div>

                  {showPlanForm && (
                    <div className="bg-slate-900 border border-indigo-500/30 p-6 rounded-2xl space-y-4">
                      <h4 className="font-bold text-sm text-white">
                        {editingPlanId ? "Editar Plan Comercial" : "Crear Nuevo Plan Comercial"}
                      </h4>
                      <form onSubmit={handleSaveSubscriptionPlan} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Código Único (Ej. BASIC, PRO)</label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: ENTERPRISE_2026"
                              value={planFormData.code}
                              onChange={(e) => setPlanFormData({ ...planFormData, code: e.target.value })}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Nombre Comercial</label>
                            <input
                              type="text"
                              required
                              placeholder="Ej: Plan Enterprise Avanzado"
                              value={planFormData.name}
                              onChange={(e) => setPlanFormData({ ...planFormData, name: e.target.value })}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Créditos Asignados</label>
                            <input
                              type="number"
                              required
                              value={planFormData.credits_allocated}
                              onChange={(e) => setPlanFormData({ ...planFormData, credits_allocated: parseInt(e.target.value) || 0 })}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Tarifa Mensual (COP)</label>
                            <input
                              type="number"
                              required
                              value={planFormData.monthly_fee}
                              onChange={(e) => setPlanFormData({ ...planFormData, monthly_fee: parseFloat(e.target.value) || 0 })}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Costo Crédito Adicional (COP)</label>
                            <input
                              type="number"
                              required
                              value={planFormData.additional_credit_fee}
                              onChange={(e) => setPlanFormData({ ...planFormData, additional_credit_fee: parseFloat(e.target.value) || 0 })}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-400 mb-1">Estado del Plan</label>
                            <select
                              value={planFormData.is_active ? "true" : "false"}
                              onChange={(e) => setPlanFormData({ ...planFormData, is_active: e.target.value === "true" })}
                              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white"
                            >
                              <option value="true">Activo (Disponible)</option>
                              <option value="false">Inactivo (Oculto)</option>
                            </select>
                          </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => {
                              setShowPlanForm(false);
                              setEditingPlanId(null);
                            }}
                            className="px-4 py-2 bg-slate-800 text-slate-300 text-xs rounded-xl cursor-pointer"
                          >
                            Cancelar
                          </button>
                          <button
                            type="submit"
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold rounded-xl cursor-pointer"
                          >
                            {editingPlanId ? "Actualizar Plan" : "Guardar Plan"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="px-5 py-3.5">Código</th>
                          <th className="px-5 py-3.5">Nombre del Plan</th>
                          <th className="px-5 py-3.5 text-right">Créditos</th>
                          <th className="px-5 py-3.5 text-right">Tarifa Mensual</th>
                          <th className="px-5 py-3.5 text-right">Costo Adicional</th>
                          <th className="px-5 py-3.5">Estado</th>
                          <th className="px-5 py-3.5 text-right">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {subscriptionPlansList.length === 0 ? (
                          <tr>
                            <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                              No hay planes comerciales registrados. Cree uno nuevo para asignarlos a las suscripciones.
                            </td>
                          </tr>
                        ) : (
                          subscriptionPlansList.map((plan) => (
                            <tr key={plan.id} className="hover:bg-slate-800/30">
                              <td className="px-5 py-4 font-mono font-bold text-indigo-400">{plan.code}</td>
                              <td className="px-5 py-4 font-semibold text-white">{plan.name}</td>
                              <td className="px-5 py-4 text-right font-mono">{plan.credits_allocated}</td>
                              <td className="px-5 py-4 text-right font-mono text-emerald-400">
                                ${Number(plan.monthly_fee || 0).toLocaleString("es-CO")}
                              </td>
                              <td className="px-5 py-4 text-right font-mono text-slate-400">
                                ${Number(plan.additional_credit_fee || 0).toLocaleString("es-CO")}
                              </td>
                              <td className="px-5 py-4">
                                <span className={`font-semibold ${plan.is_active ? "text-emerald-400" : "text-rose-400"}`}>
                                  {plan.is_active ? "Activo" : "Inactivo"}
                                </span>
                              </td>
                              <td className="px-5 py-4 text-right space-x-2 whitespace-nowrap">
                                <button
                                  type="button"
                                  onClick={() => handleEditSubscriptionPlan(plan)}
                                  title="Editar Plan"
                                  className="p-1.5 bg-slate-800 hover:bg-indigo-600/30 text-indigo-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteSubscriptionPlan(plan.id, plan.name)}
                                  title="Eliminar Plan"
                                  className="p-1.5 bg-slate-800 hover:bg-rose-600/30 text-rose-400 rounded-lg transition-colors cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
////*****
          {/* ==================================================================
              MÓDULO 3: EXPORTACIÓN MULTI-ERP
             ================================================================== */}
          {activeTab === "exportacion" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">
                  Centro de Exportación Masiva a ERPs
                </h2>
                <p className="text-sm text-slate-400">
                  Descarga de planos contables compatibles con las principales plataformas del
                  mercado.
                </p>
              </div>

              <div className="bg-slate-900/80 p-6 rounded-2xl border border-slate-800 flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <FileOutput className="w-8 h-8 text-indigo-400" />
                  <div>
                    <h4 className="font-bold text-white text-sm">
                      Exportar Movimientos Contables Causados
                    </h4>
                    <p className="text-xs text-slate-400">
                      Seleccione el software contable de destino para estructurar las partidas
                      dobles.
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <select
                    value={selectedErp}
                    onChange={(e) => setSelectedErp(e.target.value)}
                    className="bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="siigo">Siigo Nube (.xlsx)</option>
                    <option value="helisa">Helisa (.csv)</option>
                    <option value="loggro">Loggro (.xlsx)</option>
                    <option value="syscafe">SysCafé (.txt)</option>
                    <option value="alegra">Alegra (.xlsx)</option>
                    <option value="world_office">World Office (.xlsx)</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => alert(`Generando descarga para ${selectedErp.toUpperCase()}...`)}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 transition-colors cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    <span>Descargar Plano</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ==================================================================
              MÓDULO 4: FACTURACIÓN SAAS A CLIENTES (EXCLUSIVO SUPER_ADMIN)
             ================================================================== */}
          {activeTab === "facturacion" && isSuperAdmin && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-white tracking-tight">
                    Facturación & Control Comercial SaaS (SUPER_ADMIN)
                  </h2>
                  <p className="text-sm text-slate-400">
                    Consolidado de consumo de créditos, facturas causadas y estados de cuenta por
                    organización cliente.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const token = localStorage.getItem("access_token") || "";
                    loadAllMaintenanceTables(token, "SUPER_ADMIN");
                  }}
                  className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer"
                >
                  <RefreshCw className="w-4 h-4" />
                  <span>Actualizar Corte</span>
                </button>
              </div>

              {/* TARJETAS KPI FINANCIERAS */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
                <div className="bg-slate-900/80 p-5 rounded-2xl border border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase">
                    Organizaciones Clientes
                  </span>
                  <p className="text-2xl font-extrabold text-white mt-2">
                    {billingKpis.total_organizations}
                  </p>
                </div>
                <div className="bg-slate-900/80 p-5 rounded-2xl border border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase">
                    Suscripciones Activas
                  </span>
                  <p className="text-2xl font-extrabold text-indigo-400 mt-2">
                    {billingKpis.active_subscriptions}
                  </p>
                </div>
                <div className="bg-slate-900/80 p-5 rounded-2xl border border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase">
                    Facturas Causadas Totales
                  </span>
                  <p className="text-2xl font-extrabold text-amber-400 mt-2">
                    {billingKpis.total_invoices_caused}
                  </p>
                </div>
                <div className="bg-slate-900/80 p-5 rounded-2xl border border-emerald-800/40">
                  <span className="text-[11px] font-semibold text-emerald-400 uppercase">
                    Facturación Mensual (MRR)
                  </span>
                  <p className="text-2xl font-extrabold text-emerald-400 mt-2 font-mono">
                    ${Number(billingKpis.total_mrr || 0).toLocaleString("es-CO")}
                  </p>
                </div>
              </div>

              {/* TABLA DE ESTADO DE CUENTA POR ORGANIZACIÓN */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/60 uppercase text-[10px] text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="px-5 py-3.5">Organización Cliente</th>
                      <th className="px-5 py-3.5">Plan</th>
                      <th className="px-5 py-3.5 text-center">Facturas (Pend / Caus)</th>
                      <th className="px-5 py-3.5 text-right">Créditos (Usados / Asig)</th>
                      <th className="px-5 py-3.5 text-right">Valor a Facturar</th>
                      <th className="px-5 py-3.5">Estado Comercial</th>
                      <th className="px-5 py-3.5 text-right">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {billingRows.map((row) => (
                      <tr key={row.organization_id} className="hover:bg-slate-800/30">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-white">{row.organization_name}</div>
                          <div className="text-[10px] font-mono text-slate-400">
                            NIT: {row.organization_nit}
                          </div>
                        </td>
                        <td className="px-5 py-4 font-mono text-indigo-400">{row.plan_name}</td>
                        <td className="px-5 py-4 text-center font-mono">
                          <span className="text-amber-400">{row.invoices_parsed}</span> /{" "}
                          <span className="text-emerald-400 font-bold">{row.invoices_caused}</span>
                        </td>
                        <td className="px-5 py-4 text-right font-mono">
                          {row.credits_used} / {row.credits_allocated}
                        </td>
                        <td className="px-5 py-4 text-right font-mono font-bold text-emerald-400">
                          ${Number(row.monthly_fee || 0).toLocaleString("es-CO")}
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              row.is_active
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                                : "bg-rose-950 text-rose-400 border border-rose-800/50"
                            }`}
                          >
                            {row.billing_status}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right">
                          {row.is_active ? (
                            <button
                              type="button"
                              onClick={() =>
                                alert(
                                  `Pre-factura generada para ${row.organization_name} (NIT ${
                                    row.organization_nit
                                  })\nPlan: ${row.plan_name}\nCréditos consumidos: ${
                                    row.credits_used
                                  }/${row.credits_allocated}\nTotal a cobrar: $${Number(
                                    row.monthly_fee
                                  ).toLocaleString("es-CO")} COP`
                                )
                              }
                              className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white rounded-lg text-[11px] font-semibold cursor-pointer"
                            >
                              Emitir Cobro
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                setActiveTab("mantenimiento");
                                setMaintenanceSubTab("subscriptions");
                              }}
                              className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-[11px] font-semibold cursor-pointer"
                            >
                              Activar Plan
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
const API_URL = "";
let currentUser = null;
let token = localStorage.getItem("hcm_token") || null;
let registrosGlobal = [];
let medsGlobal = [];
let recuentoGlobal = [];

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  setupEvents();
  
  let fechaInput = document.getElementById("inputFechaRecuento");
  if (fechaInput) {
    let hoy = new Date().toISOString().split("T")[0];
    fechaInput.value = hoy;
  }

  if (token) {
    checkAuth();
  } else {
    showView("loginView");
  }
});

function showToast(msg, error = false) {
  const t = document.getElementById("toast");
  const toastMsg = document.getElementById("toastMsg");
  if (!t || !toastMsg) return;
  toastMsg.innerText = msg;
  t.className = "fixed bottom-5 right-5 z-50 transform transition-all duration-300 translate-y-0 opacity-100 px-4 py-3 rounded-2xl shadow-xl flex items-center gap-3 text-xs font-semibold " + (error ? "bg-rose-600" : "bg-slate-900") + " text-white";
  setTimeout(() => {
    t.classList.replace("translate-y-0", "translate-y-20");
    t.classList.replace("opacity-100", "opacity-0");
  }, 3000);
}

function showView(vid) {
  const loginV = document.getElementById("loginView");
  const mainV = document.getElementById("mainView");
  if (loginV) loginV.classList.add("hidden");
  if (mainV) mainV.classList.add("hidden");
  const target = document.getElementById(vid);
  if (target) target.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function showTab(tid) {
  ["tabCuaderno", "tabRecuento", "tabStock", "tabAdmin"].forEach(t => {
    const el = document.getElementById(t);
    if (el) el.classList.add("hidden");
  });
  
  const targetTab = document.getElementById("tab" + tid.charAt(0).toUpperCase() + tid.slice(1));
  if (targetTab) targetTab.classList.remove("hidden");
  
  ["tabBtnCuaderno", "tabBtnRecuento", "tabBtnStock", "tabBtnAdmin"].forEach(b => {
    let el = document.getElementById(b);
    if(el) {
      el.classList.remove("text-sky-600", "text-purple-700", "border-sky-600", "border-purple-700");
      el.classList.add("text-slate-500", "border-transparent");
      if(tid === "cuaderno" && b.includes("Cuaderno")) el.classList.add("text-sky-600", "border-sky-600");
      if(tid === "recuento" && b.includes("Recuento")) el.classList.add("text-sky-600", "border-sky-600");
      if(tid === "stock" && b.includes("Stock")) el.classList.add("text-sky-600", "border-sky-600");
      if(tid === "admin" && b.includes("Admin")) el.classList.add("text-purple-700", "border-purple-700");
    }
  });

  if(tid === "cuaderno") loadRegistros();
  if(tid === "recuento") loadRecuentoDiario();
  if(tid === "stock") loadStock();
  if(tid === "admin") loadAdminData();
  if (window.lucide) lucide.createIcons();
}

function openModal(id) { 
  const el = document.getElementById(id);
  if (el) el.classList.remove("hidden"); 
  if (window.lucide) lucide.createIcons();
}

function closeModal(id) { 
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden"); 
}

async function checkAuth() {
  try {
    const r = await fetch(API_URL + "/api/me", { headers: { Authorization: "Bearer " + token }});
    if(r.ok) {
      currentUser = await r.json();
      setupApp();
    } else {
      logout();
    }
  } catch(e) { 
    logout(); 
  }
}

async function doLogin(u, p) {
  try {
    const r = await fetch(API_URL + "/api/login", {
      method: "POST", 
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p })
    });
    const d = await r.json();
    if(r.ok) {
      token = d.access_token;
      localStorage.setItem("hcm_token", token);
      currentUser = d.user;
      setupApp();
      showToast("Bienvenido " + currentUser.nombre_completo);
    } else {
      showToast(d.detail || "Usuario o contrasena incorrectos", true);
    }
  } catch(e) { 
    showToast("Error de conexion con el servidor", true); 
  }
}

function logout() {
  token = null; 
  currentUser = null;
  localStorage.removeItem("hcm_token");
  showView("loginView");
}

function setupApp() {
  const nombreEl = document.getElementById("userNombre");
  const rolEl = document.getElementById("userRolBadge");
  const tabAdminEl = document.getElementById("tabBtnAdmin");
  const btnStockAdminEl = document.getElementById("btnStockAdmin");
  const btnAnotarUsoEl = document.getElementById("btnAnotarUso");
  const btnAnotarDevEl = document.getElementById("btnAnotarDev");

  if (nombreEl) nombreEl.innerText = currentUser.nombre_completo;
  if (rolEl) rolEl.innerText = currentUser.rol.toUpperCase();
  
  const isAdmin = currentUser.rol === "admin";
  const isFarmacia = currentUser.rol === "farmacia";

  if (tabAdminEl) tabAdminEl.classList.toggle("hidden", !isAdmin);
  if (btnStockAdminEl) btnStockAdminEl.classList.toggle("hidden", !isAdmin);

  // Ocultar botones de solicitud y devolucion para rol farmacia
  if (btnAnotarUsoEl) btnAnotarUsoEl.classList.toggle("hidden", isFarmacia);
  if (btnAnotarDevEl) btnAnotarDevEl.classList.toggle("hidden", isFarmacia);
  
  showView("mainView");
  showTab("cuaderno");
  loadStockSelects();
}

function abrirModalAnotar(tipo) {
  if (currentUser && currentUser.rol === "farmacia") {
    showToast("El rol Farmacia solo tiene permisos para controlar y validar", true);
    return;
  }

  const tipoInput = document.getElementById("anotarTipo");
  const titulo = document.getElementById("modalAnotarTitulo");
  const lblPac = document.getElementById("lblAnotarPaciente");
  const inPac = document.getElementById("anotarPaciente");
  const lblCant = document.getElementById("lblAnotarCant");
  const btnSubmit = document.getElementById("btnAnotarSubmit");
  const card = document.getElementById("modalAnotarCard");

  if (tipo === "devolucion") {
    tipoInput.value = "devolucion";
    titulo.innerHTML = '<i data-lucide="undo-2" class="w-5 h-5 text-rose-600"></i><span class="text-rose-700">Registrar Devolucion de Medicacion</span>';
    lblPac.innerText = "Paciente / Detalle de Devolucion *";
    inPac.placeholder = "Ej: Resto no utilizado / Devolucion de quirofano";
    lblCant.innerText = "Cantidad Devuelta (Reintegra a Deposito) *";
    btnSubmit.innerText = "Registrar Devolucion (Fondo Rojo)";
    btnSubmit.className = "px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs rounded-xl shadow-md shadow-rose-600/30";
    card.className = "bg-rose-50/50 border-2 border-rose-200 rounded-3xl p-6 max-w-md w-full shadow-2xl";
  } else {
    tipoInput.value = "uso";
    titulo.innerHTML = '<i data-lucide="file-plus-2" class="w-5 h-5 text-sky-600"></i><span>Anotar Medicamento en Paciente</span>';
    lblPac.innerText = "Nombre Completo del Paciente *";
    inPac.placeholder = "Ej: Perez, Juan Carlos";
    lblCant.innerText = "Cantidad Utilizada *";
    btnSubmit.innerText = "Guardar en Cuaderno";
    btnSubmit.className = "px-5 py-2 bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs rounded-xl shadow-md shadow-sky-600/30";
    card.className = "bg-white rounded-3xl p-6 max-w-md w-full shadow-2xl border border-slate-100";
  }

  openModal("modalAnotar");
  if (window.lucide) lucide.createIcons();
}

async function loadStockSelects() {
  try {
    const r = await fetch(API_URL + "/api/medicamentos", { headers: { Authorization: "Bearer " + token }});
    if (!r.ok) return;
    medsGlobal = await r.json();
    let sel = document.getElementById("anotarMedId");
    if (!sel) return;
    sel.innerHTML = "";
    medsGlobal.forEach(m => {
      sel.innerHTML += `<option value="${m.id}">${m.nombre} (Disponible: ${m.stock_actual})</option>`;
    });
  } catch(e) {}
}

async function loadRegistros() {
  try {
    let inputB = document.getElementById("inputBusqueda");
    let filter = inputB ? inputB.value.trim() : "";
    let url = API_URL + "/api/registros" + (filter ? "?busqueda=" + encodeURIComponent(filter) : "");
    const r = await fetch(url, { headers: { Authorization: "Bearer " + token }});
    if (!r.ok) return;
    registrosGlobal = await r.json();
    
    let tb = document.getElementById("registrosTbody");
    let mobileCards = document.getElementById("registrosMobileCards");
    
    if (tb) tb.innerHTML = "";
    if (mobileCards) mobileCards.innerHTML = "";
    
    if(!registrosGlobal.length) {
      if (tb) tb.innerHTML = '<tr><td colspan="9" class="p-8 text-center text-slate-400 font-bold">No hay registros asentados</td></tr>';
      if (mobileCards) mobileCards.innerHTML = '<div class="bg-white p-6 rounded-2xl text-center text-slate-400 font-bold text-xs border border-slate-200">No hay registros asentados</div>';
      return;
    }

    let isAdmin = currentUser && currentUser.rol === "admin";
    let isFarmacia = currentUser && (currentUser.rol === "farmacia" || isAdmin);

    registrosGlobal.forEach(rg => {
      let f_date = new Date(rg.fecha_hora).toLocaleString('es-AR', { day:'2-digit', month:'2-digit', year:'2-digit', hour:'2-digit', minute:'2-digit' });
      
      let isDevolucion = rg.tipo === "devolucion";
      let rowBgClass = isDevolucion 
        ? "bg-rose-50 hover:bg-rose-100/70 border-l-4 border-rose-500 text-rose-900" 
        : "hover:bg-slate-50";

      let tipoBadge = isDevolucion
        ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-200 text-rose-800 border border-rose-300 uppercase">Devolucion</span>`
        : `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800 border border-sky-200">Uso</span>`;

      let farmHTML = "";
      let farmMobileHTML = "";
      if (rg.control_farmacia === 1) {
        farmHTML = `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">Aprobado: ${rg.farmaceutico_nombre || 'Farmacia'}</span>`;
        farmMobileHTML = `<span class="text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1"><i data-lucide="check" class="w-3 h-3"></i> Aprobado</span>`;
      } else if (rg.control_farmacia === 2) {
        farmHTML = `<div class="inline-flex flex-col items-center">
          <span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-200 text-rose-900 border border-rose-300">Rechazado</span>
          <span class="text-[9px] text-rose-700 font-semibold italic mt-0.5" title="${rg.motivo_rechazo}">Motivo: ${rg.motivo_rechazo}</span>
        </div>`;
        farmMobileHTML = `<span class="text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1"><i data-lucide="x" class="w-3 h-3"></i> Rechazado</span>`;
      } else {
        farmHTML = `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">Pendiente</span>`;
        farmMobileHTML = `<span class="text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1"><i data-lucide="clock" class="w-3 h-3"></i> Pendiente</span>`;
      }
      
      let acts = "";
      let mobileActs = "";
      if(rg.control_farmacia === 0 && isFarmacia) {
        acts += `<button onclick="promptControl(${rg.id})" class="px-2.5 py-1 bg-teal-600 hover:bg-teal-500 text-white rounded-lg mr-1.5 font-bold text-xs shadow-sm transition">Controlar</button>`;
        mobileActs += `<button onclick="promptControl(${rg.id})" class="flex-1 py-1.5 bg-teal-600 active:bg-teal-700 text-white rounded-xl font-bold text-xs shadow-sm flex items-center justify-center gap-1"><i data-lucide="check" class="w-3.5 h-3.5"></i> Controlar</button>`;
      }
      if(isAdmin) {
        acts += `<button onclick="borrarRegistro(${rg.id})" title="Eliminar registro (Superadmin)" class="px-2 py-1 bg-rose-100 hover:bg-rose-200 text-rose-700 rounded-lg text-xs font-bold border border-rose-300 transition">Borrar</button>`;
        mobileActs += `<button onclick="borrarRegistro(${rg.id})" class="px-3 py-1.5 bg-rose-50 text-rose-700 active:bg-rose-100 rounded-xl text-xs font-bold border border-rose-200 flex items-center justify-center gap-1"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Borrar</button>`;
      }

      // 1. Desktop Table Row
      if (tb) {
        tb.innerHTML += `
          <tr class="${rowBgClass} transition-colors">
            <td class="p-3.5 font-mono text-slate-400 font-bold">#${rg.id}</td>
            <td class="p-3.5 text-slate-600 font-mono text-[11px]">${f_date}</td>
            <td class="p-3.5">${tipoBadge}</td>
            <td class="p-3.5 font-bold ${isDevolucion ? 'text-rose-950' : 'text-slate-900'}">${rg.paciente_nombre}</td>
            <td class="p-3.5 font-bold ${isDevolucion ? 'text-rose-800' : 'text-sky-900'}">${rg.medicamento_nombre}</td>
            <td class="p-3.5 text-center font-black ${isDevolucion ? 'text-rose-700 bg-rose-100/50' : 'text-slate-900 bg-slate-50/50'}">${isDevolucion ? '-' + rg.cantidad_usada : rg.cantidad_usada}</td>
            <td class="p-3.5 text-slate-700 text-xs font-semibold">${rg.tecnico_nombre}</td>
            <td class="p-3.5 text-center">${farmHTML}</td>
            <td class="p-3.5 text-right whitespace-nowrap">${acts}</td>
          </tr>
        `;
      }

      // 2. Mobile Responsive Card
      if (mobileCards) {
        let cardBg = isDevolucion ? "bg-rose-50/60 border-rose-200 text-rose-950" : "bg-white border-slate-200 text-slate-900";
        mobileCards.innerHTML += `
          <div class="${cardBg} p-3.5 rounded-2xl border shadow-xs space-y-2.5">
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-1.5">
                <span class="text-[10px] font-mono font-bold text-slate-400">#${rg.id}</span>
                ${tipoBadge}
              </div>
              <span class="text-[10px] font-mono text-slate-400 font-semibold">${f_date}</span>
            </div>

            <div>
              <div class="text-xs font-black leading-snug">${rg.paciente_nombre}</div>
              <div class="text-[11px] font-bold ${isDevolucion ? 'text-rose-700' : 'text-sky-700'} mt-0.5">${rg.medicamento_nombre}</div>
            </div>

            <div class="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
              <div class="flex items-center gap-1.5">
                <span class="text-slate-400 text-[10px]">Cantidad:</span>
                <span class="font-black px-2 py-0.5 rounded-lg ${isDevolucion ? 'bg-rose-100 text-rose-800' : 'bg-sky-50 text-sky-800 font-mono'} text-xs">${isDevolucion ? '-' + rg.cantidad_usada : rg.cantidad_usada}</span>
              </div>
              <div>${farmMobileHTML}</div>
            </div>

            <div class="text-[10px] text-slate-500 font-semibold flex items-center justify-between">
              <span>Por: <strong>${rg.tecnico_nombre}</strong></span>
              ${rg.motivo_rechazo ? `<span class="text-rose-600 italic">Rechazo: ${rg.motivo_rechazo}</span>` : ''}
            </div>

            ${mobileActs ? `<div class="flex items-center gap-2 pt-2 border-t border-slate-100">${mobileActs}</div>` : ''}
          </div>
        `;
      }
    });
    if (window.lucide) lucide.createIcons();
  } catch(e) {}
}

async function loadRecuentoDiario() {
  try {
    let fechaInput = document.getElementById("inputFechaRecuento");
    let fecha = fechaInput ? fechaInput.value : "";
    let url = API_URL + "/api/recuento-diario" + (fecha ? "?fecha=" + encodeURIComponent(fecha) : "");
    const r = await fetch(url, { headers: { Authorization: "Bearer " + token }});
    if (!r.ok) return;
    const data = await r.json();
    recuentoGlobal = data.medicamentos || [];
    
    let tbTec = document.getElementById("recuentoTecnicosTbody");
    let tbFarm = document.getElementById("recuentoFarmaciaTbody");
    let tbBalance = document.getElementById("balanceConsolidadoTbody");
    if (!tbTec || !tbFarm || !tbBalance) return;
    
    tbTec.innerHTML = "";
    tbFarm.innerHTML = "";
    tbBalance.innerHTML = "";

    let isFarmaciaOrAdmin = currentUser && (currentUser.rol === "farmacia" || currentUser.rol === "admin");

    recuentoGlobal.forEach(m => {
      // 1. Panel Tecnicos
      tbTec.innerHTML += `
        <tr class="hover:bg-slate-50 transition">
          <td class="py-2.5 font-bold text-slate-800">${m.medicamento_nombre}</td>
          <td class="py-2.5 text-center font-bold text-sky-700">${m.total_pedido_tecnico} amp</td>
          <td class="py-2.5 text-center font-bold text-rose-600">${m.total_devuelto_tecnico > 0 ? '-' + m.total_devuelto_tecnico : '0'} amp</td>
          <td class="py-2.5 text-right font-black text-slate-900 text-sm bg-slate-50/50 px-2 rounded-lg">${m.recuento_neto_tecnicos} amp</td>
        </tr>
      `;

      // 2. Panel Despacho Manual Farmacia
      let btnCargaFarm = isFarmaciaOrAdmin 
        ? `<button onclick="abrirModalDespachoFarmacia(${m.medicamento_id}, '${m.medicamento_nombre}', ${m.cantidad_despachada_farmacia}, '${m.observaciones_farmacia || ''}')" class="px-2.5 py-1 bg-teal-50 hover:bg-teal-100 text-teal-700 border border-teal-200 rounded-lg text-xs font-bold transition">Cargar Despacho</button>`
        : `<span class="text-slate-400 text-xs italic">Solo Farmacia</span>`;

      tbFarm.innerHTML += `
        <tr class="hover:bg-slate-50 transition">
          <td class="py-2.5 font-bold text-slate-800">${m.medicamento_nombre}</td>
          <td class="py-2.5 text-center font-black text-teal-800 text-sm bg-teal-50/50 px-2 rounded-lg">${m.cantidad_despachada_farmacia} amp</td>
          <td class="py-2.5 text-slate-500 text-xs italic">${m.observaciones_farmacia || (m.farmaceutico_nombre ? 'Cargado por ' + m.farmaceutico_nombre : 'Sin carga')}</td>
          <td class="py-2.5 text-right">${btnCargaFarm}</td>
        </tr>
      `;

      // 3. Tabla de Balance Diario Consolidado
      let diffBadge = "";
      if (m.diferencia_balance === 0) {
        diffBadge = `<span class="px-2.5 py-1 bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-full font-bold text-xs">Balance Exacto (0)</span>`;
      } else if (m.diferencia_balance > 0) {
        diffBadge = `<span class="px-2.5 py-1 bg-sky-100 text-sky-800 border border-sky-200 rounded-full font-bold text-xs">+${m.diferencia_balance} amp en quirofano</span>`;
      } else {
        diffBadge = `<span class="px-2.5 py-1 bg-rose-100 text-rose-800 border border-rose-200 rounded-full font-bold text-xs">${m.diferencia_balance} amp (Faltante)</span>`;
      }

      tbBalance.innerHTML += `
        <tr class="hover:bg-slate-50 transition">
          <td class="p-3 font-bold text-slate-900">${m.medicamento_nombre}</td>
          <td class="p-3 text-center font-black text-teal-700">${m.cantidad_despachada_farmacia} amp</td>
          <td class="p-3 text-center font-black text-sky-700">${m.recuento_neto_tecnicos} amp</td>
          <td class="p-3 text-center">${diffBadge}</td>
          <td class="p-3 text-right font-mono font-bold text-slate-800">${m.stock_deposito} amp</td>
        </tr>
      `;
    });
    if (window.lucide) lucide.createIcons();
  } catch(e) {}
}

function abrirModalDespachoFarmacia(medId, medNombre, cantActual, obsActual) {
  document.getElementById("despachoMedId").value = medId;
  document.getElementById("despachoMedTxt").innerText = medNombre;
  document.getElementById("despachoCantInput").value = cantActual || 0;
  document.getElementById("despachoObsInput").value = obsActual || "";
  openModal("modalDespachoFarmacia");
}

function promptControl(id) {
  let rg = registrosGlobal.find(x => x.id == id);
  if(!rg) return;
  document.getElementById("ctrlRegId").value = id;
  document.getElementById("ctrlPacienteTxt").innerText = rg.paciente_nombre + (rg.tipo === 'devolucion' ? ' (DEVOLUCION)' : '');
  document.getElementById("ctrlMedTxt").innerText = (rg.tipo === 'devolucion' ? 'Reintegro de ' : 'Uso de ') + rg.cantidad_usada + " x " + rg.medicamento_nombre;
  document.getElementById("ctrlObsInput").value = rg.observaciones || "";
  document.getElementById("ctrlMotivoRechazo").value = "";
  openModal("modalControl");
}

async function borrarRegistro(id) {
  if(!confirm("CONTROL TOTAL ADMIN: Desea eliminar definitivamente este registro de la base de datos?")) return;
  try {
    const r = await fetch(API_URL + "/api/admin/registros/" + id, {
      method: "DELETE", 
      headers: { Authorization: "Bearer " + token }
    });
    if(r.ok) { 
      showToast("Registro eliminado correctamente"); 
      loadRegistros(); 
      loadRecuentoDiario();
      loadStockSelects(); 
    } else {
      showToast("Error al borrar registro", true);
    }
  } catch(e){}
}

async function adminVaciarCuaderno() {
  if(!confirm("PELIGRO SUPERADMIN: Esta seguro de VACIAR TODOS los registros del cuaderno y despachos?")) return;
  try {
    const r = await fetch(API_URL + "/api/admin/vaciar-cuaderno", {
      method: "POST", 
      headers: { Authorization: "Bearer " + token }
    });
    if(r.ok) { 
      showToast("Cuaderno y despachos vaciados por SuperAdmin", true); 
      loadRegistros(); 
      loadRecuentoDiario(); 
    }
  } catch(e){}
}

async function loadStock() {
  try {
    const r = await fetch(API_URL + "/api/medicamentos", { headers: { Authorization: "Bearer " + token }});
    if (!r.ok) return;
    medsGlobal = await r.json();
    let c = document.getElementById("medsContainer");
    if (!c) return;
    c.innerHTML = "";
    let isAdmin = currentUser && currentUser.rol === "admin";
    
    medsGlobal.forEach(m => {
      let bts = "";
      if(isAdmin) {
        bts = `
          <button onclick="cambiarStock(${m.id}, '${m.nombre}', ${m.stock_actual})" class="text-xs bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-xl font-bold text-slate-700 transition">Modificar</button>
          <button onclick="borrarMed(${m.id})" title="Borrar Medicamento" class="text-xs bg-rose-50 hover:bg-rose-100 text-rose-700 px-2.5 py-1.5 rounded-xl font-bold transition">Eliminar</button>
        `;
      }
      
      c.innerHTML += `
        <div class="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm flex flex-col justify-between hover:border-sky-300 transition">
          <div>
            <span class="text-[10px] font-black text-sky-700 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-100 uppercase tracking-wider">Hospital Central</span>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 leading-tight mt-2 mb-4">${m.nombre}</h3>
          </div>
          <div class="flex items-end justify-between pt-4 border-t border-slate-100">
            <div>
              <div class="text-3xl font-black ${m.stock_actual < 20 ? 'text-rose-600' : 'text-slate-900'}">${m.stock_actual}</div>
              <div class="text-[11px] font-semibold text-slate-400">unidades disponibles</div>
            </div>
            <div class="flex gap-1.5">${bts}</div>
          </div>
        </div>
      `;
    });
    if (window.lucide) lucide.createIcons();
  } catch(e){}
}

async function cambiarStock(id, nombre, actual) {
  let v = prompt("Nuevo stock en deposito para " + nombre + ":", actual);
  if (v === null) return;
  let num = parseInt(v);
  if (isNaN(num) || num < 0) return showToast("Cantidad invalida", true);
  try {
    const r = await fetch(API_URL + "/api/medicamentos/" + id, {
      method: "PUT", 
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ stock_actual: num })
    });
    if(r.ok) { 
      showToast("Stock de " + nombre + " actualizado a " + num); 
      loadStock(); 
      loadStockSelects(); 
    }
  } catch(e){}
}

async function borrarMed(id) {
  if(!confirm("BORRAR MEDICAMENTO O DILUCION Y TODOS SUS REGISTROS ASOCIADOS DE LA BD. Desea continuar?")) return;
  try {
    const r = await fetch(API_URL + "/api/admin/medicamentos/" + id, {
      method: "DELETE", 
      headers: { Authorization: "Bearer " + token }
    });
    if(r.ok) { 
      showToast("Medicamento eliminado de la BD", true); 
      loadStock(); 
      loadStockSelects(); 
    }
  } catch(e){}
}

async function loadAdminData() {
  try {
    const r = await fetch(API_URL + "/api/admin/usuarios", { headers: { Authorization: "Bearer " + token }});
    if (!r.ok) return;
    let usrs = await r.json();
    let tb = document.getElementById("usuariosTbody");
    if (!tb) return;
    tb.innerHTML = "";
    usrs.forEach(u => {
      let bts = "";
      if (u.id === currentUser.id) {
        bts = '<span class="text-slate-400 text-xs italic font-semibold">Tu cuenta activa</span>';
      } else {
        bts = `
          <button onclick="adminCambiarPassUsuario(${u.id}, '${u.username}')" class="text-sky-700 bg-sky-50 hover:bg-sky-100 font-bold px-2.5 py-1 rounded-xl text-xs transition mr-1.5">Cambiar Clave</button>
          <button onclick="borrarUsr(${u.id})" class="text-rose-600 bg-rose-50 hover:bg-rose-100 font-bold px-2.5 py-1 rounded-xl text-xs transition">Borrar</button>
        `;
      }
      
      let rolBadgeClass = u.rol === "admin" 
        ? "bg-purple-50 text-purple-700 border-purple-200" 
        : (u.rol === "farmacia" ? "bg-teal-50 text-teal-700 border-teal-200" : "bg-sky-50 text-sky-700 border-sky-200");

      tb.innerHTML += `
        <tr class="hover:bg-slate-50 transition">
          <td class="p-3 text-slate-400 font-mono font-bold">#${u.id}</td>
          <td class="p-3 font-bold text-slate-900">@${u.username}</td>
          <td class="p-3 text-slate-700 font-semibold">${u.nombre_completo}</td>
          <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] uppercase font-bold border ${rolBadgeClass}">${u.rol}</span></td>
          <td class="p-3 text-right">${bts}</td>
        </tr>
      `;
    });
    if (window.lucide) lucide.createIcons();
  } catch(e){}
}

async function adminCambiarPassUsuario(id, username) {
  let nueva = prompt("Ingrese la nueva contrasena para @" + username + " (minimo 4 caracteres):");
  if (!nueva) return;
  if (nueva.length < 4) return showToast("La contrasena debe tener al menos 4 caracteres", true);

  try {
    const r = await fetch(API_URL + "/api/admin/usuarios/" + id + "/password", {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ password_nueva: nueva })
    });
    if (r.ok) {
      showToast("Contrasena actualizada para @" + username);
    } else {
      let d = await r.json();
      showToast(d.detail || "Error al actualizar contrasena", true);
    }
  } catch (e) {
    showToast("Error de conexion", true);
  }
}

async function borrarUsr(id) {
  if(!confirm("SUPERADMIN: Borrar definitivamente este usuario de la base de datos?")) return;
  try {
    const r = await fetch(API_URL + "/api/admin/usuarios/" + id, {
      method: "DELETE", 
      headers: { Authorization: "Bearer " + token }
    });
    if(r.ok) { 
      showToast("Usuario eliminado correctamente"); 
      loadAdminData(); 
    }
  } catch(e){}
}

function setupEvents() {
  const loginF = document.getElementById("loginForm");
  if (loginF) {
    loginF.addEventListener("submit", e => {
      e.preventDefault();
      doLogin(document.getElementById("loginUser").value, document.getElementById("loginPass").value);
    });
  }

  const formAn = document.getElementById("formAnotar");
  if (formAn) {
    formAn.addEventListener("submit", async e => {
      e.preventDefault();
      const bd = {
        paciente_nombre: document.getElementById("anotarPaciente").value,
        medicamento_id: parseInt(document.getElementById("anotarMedId").value),
        cantidad_usada: parseInt(document.getElementById("anotarCant").value),
        tipo: document.getElementById("anotarTipo").value
      };
      try {
        const r = await fetch(API_URL + "/api/registros", {
          method: "POST", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify(bd)
        });
        if(r.ok) { 
          showToast(bd.tipo === 'devolucion' ? "Devolucion registrada con exito" : "Anotacion guardada y stock descontado"); 
          closeModal("modalAnotar"); 
          formAn.reset();
          loadRegistros(); 
          loadRecuentoDiario();
          loadStockSelects(); 
        } else { 
          let d = await r.json(); 
          showToast(d.detail || "Error al anotar", true); 
        }
      } catch(e){ showToast("Error de conexion", true); }
    });
  }

  const formAp = document.getElementById("formAprobar");
  if (formAp) {
    formAp.addEventListener("submit", async e => {
      e.preventDefault();
      let id = document.getElementById("ctrlRegId").value;
      let obs = document.getElementById("ctrlObsInput").value;
      try {
        const r = await fetch(API_URL + "/api/registros/" + id + "/aprobar", {
          method: "PUT", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify({ observaciones: obs })
        });
        if(r.ok) { 
          showToast("Registro aprobado y verificado por Farmacia"); 
          closeModal("modalControl"); 
          loadRegistros(); 
          loadRecuentoDiario();
        } else showToast("Error al aprobar", true);
      } catch(e){}
    });
  }

  const formRech = document.getElementById("formRechazar");
  if (formRech) {
    formRech.addEventListener("submit", async e => {
      e.preventDefault();
      let id = document.getElementById("ctrlRegId").value;
      let mot = document.getElementById("ctrlMotivoRechazo").value;
      if(!mot.trim()) return showToast("Debe indicar el motivo del rechazo", true);
      try {
        const r = await fetch(API_URL + "/api/registros/" + id + "/rechazar", {
          method: "PUT", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify({ motivo_rechazo: mot })
        });
        if(r.ok) { 
          showToast("Registro RECHAZADO y stock corregido", true); 
          closeModal("modalControl"); 
          loadRegistros(); 
          loadRecuentoDiario();
          loadStockSelects(); 
        } else {
          let d = await r.json(); 
          showToast(d.detail || "Error al rechazar", true); 
        }
      } catch(e){}
    });
  }

  const formDespacho = document.getElementById("formDespachoFarmacia");
  if (formDespacho) {
    formDespacho.addEventListener("submit", async e => {
      e.preventDefault();
      let fechaInput = document.getElementById("inputFechaRecuento");
      let fecha = fechaInput ? fechaInput.value : new Date().toISOString().split("T")[0];
      let bd = {
        fecha: fecha,
        medicamento_id: parseInt(document.getElementById("despachoMedId").value),
        cantidad_despachada: parseInt(document.getElementById("despachoCantInput").value),
        observaciones: document.getElementById("despachoObsInput").value
      };
      try {
        const r = await fetch(API_URL + "/api/farmacia/despacho-diario", {
          method: "POST", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify(bd)
        });
        if(r.ok) { 
          showToast("Despacho manual de Farmacia guardado"); 
          closeModal("modalDespachoFarmacia"); 
          loadRecuentoDiario(); 
        } else {
          let d = await r.json();
          showToast(d.detail || "Error al guardar despacho", true);
        }
      } catch(e){ showToast("Error de conexion", true); }
    });
  }

  const formNMed = document.getElementById("formNuevoMed");
  if (formNMed) {
    formNMed.addEventListener("submit", async e => {
      e.preventDefault();
      let bd = { 
        nombre: document.getElementById("nuevoMedNombre").value, 
        stock_actual: parseInt(document.getElementById("nuevoMedStock").value) 
      };
      try {
        const r = await fetch(API_URL + "/api/medicamentos", {
          method: "POST", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify(bd)
        });
        if(r.ok) { 
          showToast("Medicamento o Dilucion agregado correctamente"); 
          closeModal("modalNuevoMed"); 
          formNMed.reset();
          loadStock(); 
          loadStockSelects(); 
        } else {
          let d = await r.json();
          showToast(d.detail || "Solo el Administrador puede agregar medicamentos", true);
        }
      } catch(e){ showToast("Error de conexion", true); }
    });
  }

  const formNUsr = document.getElementById("formNuevoUsuario");
  if (formNUsr) {
    formNUsr.addEventListener("submit", async e => {
      e.preventDefault();
      let bd = {
        nombre_completo: document.getElementById("usrNombre").value,
        username: document.getElementById("usrUser").value,
        password: document.getElementById("usrPass").value,
        rol: document.getElementById("usrRol").value
      };
      try {
        const r = await fetch(API_URL + "/api/admin/usuarios", {
          method: "POST", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify(bd)
        });
        if(r.ok) { 
          showToast("Usuario creado en el sistema HCM"); 
          closeModal("modalNuevoUsuario"); 
          formNUsr.reset();
          loadAdminData(); 
        } else {
          let d = await r.json();
          showToast(d.detail || "Error al crear usuario", true);
        }
      } catch(e){ showToast("Error de conexion", true); }
    });
  }

  const formPass = document.getElementById("formCambiarPass");
  if (formPass) {
    formPass.addEventListener("submit", async e => {
      e.preventDefault();
      let bd = {
        password_actual: document.getElementById("passActual").value,
        password_nueva: document.getElementById("passNueva").value
      };
      try {
        const r = await fetch(API_URL + "/api/perfil/cambiar-password", {
          method: "POST", 
          headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
          body: JSON.stringify(bd)
        });
        if(r.ok) { 
          showToast("Contrasena actualizada exitosamente"); 
          closeModal("modalCambiarPass"); 
          formPass.reset();
        } else {
          let d = await r.json();
          showToast(d.detail || "Error al cambiar contrasena", true);
        }
      } catch(e){ showToast("Error de conexion", true); }
    });
  }
}
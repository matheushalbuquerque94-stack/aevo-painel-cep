"""Mapping AEVO plant_id -> FusionSolar station DN.

ATENCAO: Esta lista foi gerada automaticamente por huawei/build_mapping.py
usando matching fuzzy de nomes. REVISE MANUALMENTE antes de habilitar no ETL.

Estrutura:
  HUAWEI_MAP[plant_id] = {"dn": "NE=...", "login": "aevomaster"}

Para adicionar plantas que nao foram detectadas pelo matcher:
  1. Rode: python -m huawei.fusionsolar --user aevomaster --cmd stations
  2. Copie o DN da estacao FusionSolar correspondente
  3. Cole aqui mapeando p/ plant_id do AEVO
"""

# ── MATCHES EXATOS (score=1.00) — confirmados manualmente ───────────────
HUAWEI_MAP = {
    # plant_id -> {"dn": FusionSolar DN, "login": qual conta usar}
    458:  {"dn": "NE=33970759", "login": "aevomaster"},  # Marca - UFV Juparanã 1
    457:  {"dn": "NE=33967413", "login": "aevomaster"},  # Marca - UFV Juparanã 2
    1257: {"dn": "NE=33978610", "login": "aevomaster"},  # São Francisco 1
    538:  {"dn": "NE=33978622", "login": "aevomaster"},  # São Francisco 2
    539:  {"dn": "NE=33978640", "login": "aevomaster"},  # São Francisco 3
    1250: {"dn": "NE=33978674", "login": "aevomaster"},  # saofrancisco -> SF5 (revisar)
    824:  {"dn": "NE=33853072", "login": "aevomaster"},  # Taiobeiras 1
    825:  {"dn": "NE=33741574", "login": "aevomaster"},  # Taiobeiras 2
    826:  {"dn": "NE=33740198", "login": "aevomaster"},  # Taiobeiras 3
    1917: {"dn": "NE=46380820", "login": "aevomaster"},  # UFV Coroados 1
    1960: {"dn": "NE=46380822", "login": "aevomaster"},  # UFV Coroados 2
    1921: {"dn": "NE=46380816", "login": "aevomaster"},  # UFV Florestópolis 2
    1919: {"dn": "NE=46380856", "login": "aevomaster"},  # UFV Jaíba
    1920: {"dn": "NE=46380826", "login": "aevomaster"},  # UFV Presidente Epitácio
    1918: {"dn": "NE=46380824", "login": "aevomaster"},  # UFV Riolândia 1
    464:  {"dn": "NE=35498860", "login": "aevomaster"},  # UFV Xuri MV1
    465:  {"dn": "NE=35498878", "login": "aevomaster"},  # UFV Xuri MV2
    468:  {"dn": "NE=35498992", "login": "aevomaster"},  # UFV Xuri MV3
    1261: {"dn": "NE=38413012", "login": "aevomaster"},  # araguari
    500:  {"dn": "NE=33858558", "login": "aevomaster"},  # mimoso
    1251: {"dn": "NE=35236132", "login": "aevomaster"},  # talisma
    1247: {"dn": "NE=35211582", "login": "aevomaster"},  # olhosdagua
    1244: {"dn": "NE=33982048", "login": "aevomaster"},  # fazhorizonte
    1245: {"dn": "NE=33846876", "login": "aevomaster"},  # patrociniodomuriae
    1365: {"dn": "NE=42521458", "login": "aevomaster"},  # marcelino1
}

# ── A REVISAR pelo usuario (provavelmente certos mas com nomes diferentes) ──
TO_REVIEW = {
    # plant_id (aevo)   |  candidato FusionSolar       | observacao
    # 1366: marcelino2 -> NE=42515154 (UFV Marcelino II) — confirmar
    # 1262: querencia -> NE=33968725 (Querência 2)       — verif se eh 1 ou 2
    # 827:  Salinas -> NE=33759743 (UFV Salinas 1)       — confirmar
    # 1936: planura -> NE=51952980 (UFV Planura I) ou NE=52020440 (UFV Planura II) — qual?
    # 1934: UFV Riolândia 2 -> ??? (so existe Riolândia 1 no FusionSolar)
    # 1957: UFV Florestópolis 1 -> ??? (so existe Florestópolis 2)
    # 1958: UFV Florestópolis 3 -> ??? (so existe Florestópolis 2)
}

# ── Estacoes FusionSolar SEM AEVO (precisam ser cadastradas?) ───────────
FS_SEM_AEVO = [
    ("NE=55889800", "UFV Santa Rita de Caldas 01"),
    ("NE=53332506", "UFV Pedro Leopoldo"),
    ("NE=53128732", "UFV Andradas 01"),
    ("NE=52617864", "UFV Sete Lagoas 07"),
    ("NE=52612424", "UFV Sete Lagoas 06"),
    ("NE=52020440", "UFV Planura II"),
    ("NE=51779652", "UFV Santa Rita de Caldas 03"),
    ("NE=46245024", "UFV Porteirinha"),
    ("NE=42515154", "UFV Marcelino II"),
    ("NE=35928554", "UFV Pará de Minas"),
    ("NE=33978658", "UFV São Francisco 4"),
    ("NE=33968695", "UFV Querência 1"),
]

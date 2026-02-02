from dataclasses import dataclass

@dataclass
class EmpresaDTO:
    nome_fantasia: str
    cnpj: str
    telefone_principal: str | None
    telefone_secundario: str | None
    email: str | None
    cidade: str
    uf: str
    cnae: str

    
    @property
    def localizacao(self) -> str:
        return f"{self.cidade} - {self.uf}"
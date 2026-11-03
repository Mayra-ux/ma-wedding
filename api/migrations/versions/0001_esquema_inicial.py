"""Esquema inicial (fase I-2).

Modelo: docs/architecture/02-modelo-de-datos.md. Cada restricción cita la regla
que protege (M1–M14) o el ADR de origen. Se ejecuta con el usuario de
migraciones; al final otorga al usuario de ejecución solo permisos de datos.

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""

import re

from alembic import context, op

from app.config import Settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ROLES_BODA = (
    "Papás de la novia",
    "Papás del novio",
    "Hermano/a de la novia",
    "Hermano/a del novio",
    "Padrinos de velación",
    "Padrinos de lazo",
    "Padrinos de arras",
    "Padrinos de anillos",
    "Dama de honor",
    "Caballero del novio",
    "Paje",
    "Ofrendas",
    "Otro",
)
MOTIVOS_REVISION = (
    "pases_inconsistentes",
    "lado_invalido",
    "grupo_invalido",
    "telefono_invalido",
    "rol_invalido",
)


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def _runtime_role() -> str:
    role = context.config.attributes.get("runtime_role") or Settings().db_runtime_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise RuntimeError("Rol de ejecución inválido")
    return role


E164 = r"'^\+[1-9][0-9]{7,14}$'"  # M11 (sug. aprobada): forma E.164; la API normaliza a +52


def upgrade() -> None:
    # ---------------------------------------------------------------- configuración
    op.execute(
        """
        CREATE TABLE configuracion_evento (
            id               smallint PRIMARY KEY CONSTRAINT configuracion_unica CHECK (id = 1),
            cierre_plazo     timestamptz NOT NULL,
            congelamiento    timestamptz NOT NULL,
            fecha_borrado_1  date NOT NULL,
            fecha_borrado_2  date NOT NULL,
            CONSTRAINT configuracion_orden_plazo CHECK (cierre_plazo < congelamiento),
            CONSTRAINT configuracion_orden_borrado CHECK (
                (congelamiento AT TIME ZONE 'UTC')::date < fecha_borrado_1
                AND fecha_borrado_1 < fecha_borrado_2
            )
        );
        -- Valores iniciales oficiales (CLAUDE.md, ADR 0010 y 0016).
        INSERT INTO configuracion_evento VALUES
            (1, '2027-02-07T00:00:00-06:00', '2027-03-07T00:00:00-06:00',
             '2027-04-05', '2027-06-04');
        """
    )

    # ---------------------------------------------------------------- invitación
    op.execute(
        f"""
        CREATE TABLE invitacion (
            id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            codigo                  text NOT NULL
                CONSTRAINT invitacion_codigo_unico UNIQUE
                CONSTRAINT invitacion_codigo_formato CHECK (codigo ~ '^INV-[0-9]{{3,}}$'),
            no_planner              integer CONSTRAINT invitacion_no_planner_positivo
                                        CHECK (no_planner > 0),
            nombre_mostrar          varchar(120) NOT NULL
                CONSTRAINT invitacion_nombre_no_vacio CHECK (btrim(nombre_mostrar) <> ''),
            adultos                 integer NOT NULL
                CONSTRAINT invitacion_adultos_min CHECK (adultos >= 1),
            ninos_autorizados       integer NOT NULL DEFAULT 0
                CONSTRAINT invitacion_ninos_no_negativo CHECK (ninos_autorizados >= 0),
            infantes                integer NOT NULL DEFAULT 0
                CONSTRAINT invitacion_infantes_no_negativo CHECK (infantes >= 0),
            pases                   integer GENERATED ALWAYS AS
                                        (adultos + ninos_autorizados) STORED,
            pases_planner_original  integer
                CONSTRAINT invitacion_pases_planner_no_negativo
                CHECK (pases_planner_original >= 0),
            lado                    text CONSTRAINT invitacion_lado_catalogo
                                        CHECK (lado IN ('Novia', 'Novio', 'Ambos')),
            grupo                   text CONSTRAINT invitacion_grupo_catalogo
                                        CHECK (grupo IN ('Familia', 'Amigos', 'Trabajo', 'Otro')),
            mesa                    integer CONSTRAINT invitacion_mesa_positiva CHECK (mesa > 0),
            nota_interna            varchar(500),
            telefono_principal      text CONSTRAINT invitacion_telefono_e164
                                        CHECK (telefono_principal ~ {E164}),
            contacto_alterno_nombre varchar(120),
            contacto_alterno_tel    text CONSTRAINT invitacion_tel_alterno_e164
                                        CHECK (contacto_alterno_tel ~ {E164}),
            requiere_revision       boolean NOT NULL DEFAULT false,
            motivos_revision        text[] NOT NULL DEFAULT '{{}}'
                CONSTRAINT invitacion_motivos_catalogo
                CHECK (motivos_revision <@ ARRAY[{_sql_list(MOTIVOS_REVISION)}]::text[]),
            desbloqueada_hasta      timestamptz,
            enlace_enviado_en       timestamptz,
            enlace_enviado_origen   text CONSTRAINT invitacion_envio_origen_catalogo
                                        CHECK (enlace_enviado_origen IN ('whatsapp', 'manual')),
            archivada_en            timestamptz,
            creada_en               timestamptz NOT NULL DEFAULT now(),
            actualizada_en          timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT invitacion_revision_coherente
                CHECK (requiere_revision = (cardinality(motivos_revision) > 0)),
            CONSTRAINT invitacion_envio_coherente
                CHECK ((enlace_enviado_en IS NULL) = (enlace_enviado_origen IS NULL))
        );

        CREATE TABLE invitacion_rol (
            invitacion_id bigint NOT NULL REFERENCES invitacion (id) ON DELETE CASCADE,
            rol           text NOT NULL CONSTRAINT invitacion_rol_catalogo
                              CHECK (rol IN ({_sql_list(ROLES_BODA)})),
            CONSTRAINT invitacion_rol_unico PRIMARY KEY (invitacion_id, rol)
        );
        """
    )

    # ---------------------------------------------------------------- respuestas
    op.execute(
        """
        CREATE TABLE version_respuesta (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            invitacion_id bigint NOT NULL REFERENCES invitacion (id) ON DELETE CASCADE,
            numero        integer NOT NULL CONSTRAINT version_numero_positivo CHECK (numero >= 1),
            vigente       boolean NOT NULL,
            asiste        boolean NOT NULL,
            confirmados   integer NOT NULL,
            alergias      varchar(200)
                CONSTRAINT version_alergias_null_si_vacio
                CHECK (alergias IS NULL OR btrim(alergias) <> ''),
            mensaje       varchar(500),
            origen        text NOT NULL
                CONSTRAINT version_origen_catalogo CHECK (origen IN ('invitado', 'admin')),
            actor         varchar(254),
            creada_en     timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT version_numero_unico UNIQUE (invitacion_id, numero),
            CONSTRAINT version_asistencia_coherente CHECK (
                (NOT asiste AND confirmados = 0 AND alergias IS NULL)
                OR (asiste AND confirmados >= 1)
            ),
            CONSTRAINT version_actor_coherente CHECK ((origen = 'admin') = (actor IS NOT NULL))
        );
        -- M4 / B1: como máximo una versión vigente por invitación.
        CREATE UNIQUE INDEX version_una_vigente
            ON version_respuesta (invitacion_id) WHERE vigente;
        """
    )

    # ---------------------------------------------------------------- enlaces
    op.execute(
        """
        CREATE TABLE enlace (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            invitacion_id bigint NOT NULL REFERENCES invitacion (id) ON DELETE CASCADE,
            hmac_token    bytea NOT NULL
                CONSTRAINT enlace_hmac_unico UNIQUE
                CONSTRAINT enlace_hmac_longitud CHECK (octet_length(hmac_token) = 32),
            token_cifrado bytea NOT NULL
                CONSTRAINT enlace_cifrado_no_vacio CHECK (octet_length(token_cifrado) > 28),
            id_llave      text NOT NULL
                CONSTRAINT enlace_id_llave_formato CHECK (id_llave ~ '^[a-z0-9_-]{1,32}$'),
            creado_en     timestamptz NOT NULL DEFAULT now(),
            revocado_en   timestamptz
        );
        -- M7: como máximo un enlace activo por invitación.
        CREATE UNIQUE INDEX enlace_uno_activo
            ON enlace (invitacion_id) WHERE revocado_en IS NULL;
        """
    )

    # ---------------------------------------------------------------- sesiones y auditoría
    op.execute(
        """
        CREATE TABLE sesion_admin (
            hash_sesion  bytea PRIMARY KEY
                CONSTRAINT sesion_hash_longitud CHECK (octet_length(hash_sesion) = 32),
            correo       varchar(254) NOT NULL,
            secreto_csrf bytea NOT NULL,
            creada_en    timestamptz NOT NULL DEFAULT now(),
            expira_en    timestamptz NOT NULL,
            CONSTRAINT sesion_expira_despues CHECK (expira_en > creada_en)
        );

        CREATE TABLE evento_auditoria (
            id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            actor             varchar(254) NOT NULL,
            accion            text NOT NULL
                CONSTRAINT auditoria_accion_formato CHECK (accion ~ '^[a-z_.]{1,64}$'),
            codigo_invitacion text
                CONSTRAINT auditoria_codigo_formato CHECK (codigo_invitacion ~ '^INV-[0-9]{3,}$'),
            detalle           jsonb NOT NULL DEFAULT '{}'::jsonb,
            creado_en         timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # ---------------------------------------------------------------- disparadores
    op.execute(
        """
        -- Marca de actualización.
        CREATE FUNCTION invitacion_tocar() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.actualizada_en := now();
            RETURN NEW;
        END $$;
        CREATE TRIGGER invitacion_tocar BEFORE UPDATE ON invitacion
            FOR EACH ROW EXECUTE FUNCTION invitacion_tocar();

        -- M6: no bajar pases por debajo de los confirmados vigentes.
        -- (En un BEFORE trigger la columna generada aún no está calculada.)
        CREATE FUNCTION invitacion_pases_no_bajo_confirmados() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            vigentes integer;
        BEGIN
            SELECT confirmados INTO vigentes
              FROM version_respuesta
             WHERE invitacion_id = NEW.id AND vigente;
            IF vigentes IS NOT NULL
               AND NEW.adultos + NEW.ninos_autorizados < vigentes THEN
                RAISE EXCEPTION 'pases_bajo_confirmados'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'invitacion_pases_no_bajo_confirmados';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER invitacion_pases_no_bajo_confirmados
            BEFORE UPDATE OF adultos, ninos_autorizados ON invitacion
            FOR EACH ROW EXECUTE FUNCTION invitacion_pases_no_bajo_confirmados();

        -- M5: confirmados ≤ pases. FOR SHARE impide que otra transacción baje los
        -- pases mientras se inserta la versión.
        CREATE FUNCTION version_confirmados_no_exceden_pases() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            pases_inv integer;
        BEGIN
            SELECT pases INTO pases_inv FROM invitacion
             WHERE id = NEW.invitacion_id FOR SHARE;
            IF NEW.confirmados > pases_inv THEN
                RAISE EXCEPTION 'confirmados_exceden_pases'
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'version_confirmados_no_exceden_pases';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER version_confirmados_no_exceden_pases
            BEFORE INSERT ON version_respuesta
            FOR EACH ROW EXECUTE FUNCTION version_confirmados_no_exceden_pases();

        -- M9: versiones inmutables. Solo se permite retirar la vigencia (true → false)
        -- y vaciar alergias (purga del 5 abr). El borrado lo hace solo la purga.
        CREATE FUNCTION version_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.id, NEW.invitacion_id, NEW.numero, NEW.asiste, NEW.confirmados,
                NEW.mensaje, NEW.origen, NEW.actor, NEW.creada_en)
               IS DISTINCT FROM
               (OLD.id, OLD.invitacion_id, OLD.numero, OLD.asiste, OLD.confirmados,
                OLD.mensaje, OLD.origen, OLD.actor, OLD.creada_en)
               OR (NEW.vigente AND NOT OLD.vigente)
               OR (NEW.alergias IS DISTINCT FROM OLD.alergias AND NEW.alergias IS NOT NULL)
            THEN
                RAISE EXCEPTION 'version_inmutable'
                    USING ERRCODE = 'check_violation', CONSTRAINT = 'version_inmutable';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER version_inmutable BEFORE UPDATE ON version_respuesta
            FOR EACH ROW EXECUTE FUNCTION version_inmutable();
        """
    )

    # ---------------------------------------------------------------- permisos (ADR 0019)
    app = _runtime_role()
    op.execute(
        f"""
        REVOKE ALL ON SCHEMA public FROM PUBLIC;
        GRANT USAGE ON SCHEMA public TO {app};
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

        GRANT SELECT ON configuracion_evento TO {app};
        GRANT SELECT, INSERT, UPDATE, DELETE ON invitacion TO {app};
        GRANT SELECT, INSERT, DELETE ON invitacion_rol, sesion_admin, evento_auditoria TO {app};
        GRANT SELECT, INSERT, DELETE ON version_respuesta TO {app};
        GRANT UPDATE (vigente, alergias) ON version_respuesta TO {app};
        GRANT SELECT, INSERT, DELETE ON enlace TO {app};
        GRANT UPDATE (revocado_en, hmac_token, token_cifrado, id_llave) ON enlace TO {app};
        GRANT EXECUTE ON FUNCTION
            invitacion_tocar(), invitacion_pases_no_bajo_confirmados(),
            version_confirmados_no_exceden_pases(), version_inmutable()
            TO {app};
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS evento_auditoria, sesion_admin, enlace, version_respuesta,
            invitacion_rol, invitacion, configuracion_evento CASCADE;
        DROP FUNCTION IF EXISTS invitacion_tocar(), invitacion_pases_no_bajo_confirmados(),
            version_confirmados_no_exceden_pases(), version_inmutable();
        """
    )

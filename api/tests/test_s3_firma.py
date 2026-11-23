"""Firma AWS SigV4 propia (app/s3.py) contra los ejemplos oficiales de AWS.

Valores publicados por AWS en «Signature Calculations for the Authorization Header»
(documentación de Amazon S3) y en la suite de pruebas de SigV4 («get-vanilla»).
Las credenciales son las de ejemplo de AWS, no reales.
"""

from datetime import UTC, datetime

from app.s3 import VACIO, Credenciales, firmar

S3_EJEMPLO = Credenciales(
    "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1", "s3"
)
MOMENTO_S3 = datetime(2013, 5, 24, tzinfo=UTC)
HOST_S3 = "examplebucket.s3.amazonaws.com"


def _firma(encabezados: dict[str, str]) -> str:
    return encabezados["authorization"].rsplit("Signature=", 1)[1]


def test_ejemplo_get_object() -> None:
    h = firmar(
        S3_EJEMPLO,
        "GET",
        "/test.txt",
        {},
        {"host": HOST_S3, "range": "bytes=0-9", "x-amz-content-sha256": VACIO},
        VACIO,
        MOMENTO_S3,
    )
    assert h["x-amz-date"] == "20130524T000000Z"
    assert "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date" in h["authorization"]
    assert _firma(h) == "f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"


def test_ejemplo_put_object() -> None:
    cuerpo_hash = "44ce7dd67c959e0d3524ffac1771dfbba87d2b6b4b4e99e42034a8b803f8b072"
    h = firmar(
        S3_EJEMPLO,
        "PUT",
        "/test$file.text",
        {},
        {
            "host": HOST_S3,
            "date": "Fri, 24 May 2013 00:00:00 GMT",
            "x-amz-storage-class": "REDUCED_REDUNDANCY",
            "x-amz-content-sha256": cuerpo_hash,
        },
        cuerpo_hash,
        MOMENTO_S3,
    )
    assert _firma(h) == "98ad721746da40c64f1a55b78f14c238d841ea1380cd77a1b5971af0ece108bd"


def test_ejemplo_list_objects() -> None:
    h = firmar(
        S3_EJEMPLO,
        "GET",
        "/",
        {"max-keys": "2", "prefix": "J"},
        {"host": HOST_S3, "x-amz-content-sha256": VACIO},
        VACIO,
        MOMENTO_S3,
    )
    assert _firma(h) == "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7"


def test_suite_sigv4_get_vanilla() -> None:
    cred = Credenciales(
        "AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "us-east-1", "service"
    )
    h = firmar(
        cred,
        "GET",
        "/",
        {},
        {"host": "example.amazonaws.com"},
        VACIO,
        datetime(2015, 8, 30, 12, 36, tzinfo=UTC),
    )
    assert _firma(h) == "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"

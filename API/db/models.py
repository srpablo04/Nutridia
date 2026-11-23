from typing import Optional, List
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Clase base de los modelos SQLAlchemy.

class Base(DeclarativeBase):
    pass

# Almacena los alimentos y sus nutrientes por 100 g.
# Relaciona cada alimento con sus porciones.

class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)

    calories: Mapped[Optional[float]]
    protein: Mapped[Optional[float]]
    fat: Mapped[Optional[float]]
    carbs: Mapped[Optional[float]]
    alcohol: Mapped[Optional[float]]
    fiber: Mapped[Optional[float]]
    sugars: Mapped[Optional[float]]
    sat_fat: Mapped[Optional[float]]
    cholesterol: Mapped[Optional[float]]
    sodium: Mapped[Optional[float]]
    potassium: Mapped[Optional[float]]
    calcium: Mapped[Optional[float]]
    iron: Mapped[Optional[float]]
    magnesium: Mapped[Optional[float]]
    vit_c: Mapped[Optional[float]]
    vit_a: Mapped[Optional[float]]
    vit_d: Mapped[Optional[float]]
    folate: Mapped[Optional[float]]
    vit_b12: Mapped[Optional[float]]

    portions: Mapped[List["Portion"]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )

    # Índice GIN para búsquedas por similitud de nombre; requiere pg_trgm.

    __table_args__ = (
        Index(
            "idx_foods_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

# Almacena la unidad de medida de cada nutriente.

class NutrientUnit(Base):
    __tablename__ = "nutrient_units"

    name: Mapped[str] = mapped_column(primary_key=True)
    unit: Mapped[str] = mapped_column(nullable=False)

# Almacena las porciones de cada alimento con su cantidad, unidad y peso en gramos.

class Portion(Base):
    __tablename__ = "portions"

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"))

    amount: Mapped[Optional[float]]
    measure_unit: Mapped[Optional[str]]
    gram_weight: Mapped[Optional[float]]
    description: Mapped[Optional[str]]

    food: Mapped["Food"] = relationship(back_populates="portions")

    # Índice para localizar las porciones asociadas a un alimento.

    __table_args__ = (
        Index("idx_portions_food_id", "food_id"),
    )
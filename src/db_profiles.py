
from sqlalchemy import select
from models_sql import Session, Profile


def get_all_profiles():

    with Session() as session:
        return [p.name for p in session.scalars(select(Profile)).all()]


def load_profile(name):

    session = Session()
    profile = session.query(Profile).filter_by(name=name).first()
    if not profile:
        return {}

    data = profile.filter_data

    data["my_location"] = profile.my_location
    data["latitude"] = profile.latitude
    data["longitude"] = profile.longitude

    data["resume"] = profile.resume

    return data


def save_profile(name, my_location=None, latitude=None, longitude=None, filter_data=None, resume=None):

    session = Session()
    profile = session.query(Profile).filter_by(name=name).first()

    if profile:

        if my_location is not None:
            profile.my_location = my_location

        if latitude is not None and longitude is not None:
            profile.latitude = latitude
            profile.longitude = longitude

        if filter_data is not None:
            profile.filter_data = filter_data

        if resume is not None:
            profile.resume = resume

    else:

        profile = Profile(
            name=name,
            latitude=latitude,
            longitude=longitude,
            filter_data=filter_data,
            resume=resume
        )
        session.add(profile)

    session.commit()

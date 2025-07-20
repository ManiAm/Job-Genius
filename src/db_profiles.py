
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

    data["resume_filename"] = profile.resume_filename
    data["resume_binary"] = profile.resume_binary
    data["resume_text"] = profile.resume_text

    return data


def save_profile(
    profile_name,
    my_location=None,
    latitude=None,
    longitude=None,
    filter_data=None,
    resume_filename=None,
    resume_binary=None):

    db = Session()

    try:

        profile = db.query(Profile).filter(Profile.name == profile_name).first()

        if profile:

            if my_location is not None:
                profile.my_location = my_location

            if latitude is not None and longitude is not None:
                profile.latitude = latitude
                profile.longitude = longitude

            if filter_data is not None:
                profile.filter_data = filter_data

            if resume_filename is not None:
                profile.resume_filename = resume_filename

            if resume_binary is not None:
                profile.resume_binary = resume_binary

        else:

            profile = Profile(
                name=profile_name,
                latitude=latitude,
                longitude=longitude,
                filter_data=filter_data,
                resume_filename=resume_filename,
                resume_binary=resume_binary
            )

            db.add(profile)

        db.commit()

    except Exception as e:
        print(f"Error saving profile: {e}")
        db.rollback()

    finally:
        db.close()


def clear_resume(profile_name):

    session = Session()

    try:

        profile = session.query(Profile).filter(Profile.name == profile_name).first()
        if not profile:
            return

        # Clear all resume-related fields
        profile.resume_filename = None
        profile.resume_binary = None
        profile.resume_text = None
        profile.resume_summary = None

        session.commit()

    except Exception as e:
        session.rollback()
        print(f"❌ Failed to clear resume for {profile_name}: {e}")
        raise

    finally:
        session.close()

